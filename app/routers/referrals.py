from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import DATABASE_URL, get_control_engine, get_tenant_engine
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.db import get_db
from app.dependencies.module_gate import require_module
from app.models.appointment import AdmissionStatus, PatientAdmission
from app.models.clinical import ClinicalNote, RecordDiagnosis
from app.models.cross_tenant_referral import CrossTenantReferralIndex
from app.models.encounter import Encounter
from app.models.patient import Gender, InsuranceType, Patient
from app.models.referral import Interconsult, PublicAccessToken, Referral, ReferralStatus, ReferralType
from app.models.tenant import Tenant, User, UserRole
from app.routers._utils import audit_mutation, commit_or_409, data_for_create, data_for_model, get_by_id_or_404, model_to_dict
from app.schemas.referral import (
    CrossTenantEncounterDiagnosis,
    CrossTenantEncounterNote,
    CrossTenantEncounterSummary,
    CrossTenantHistoryRead,
    CrossTenantPatientSummary,
    CrossTenantReferralStatusUpdate,
    ImportedPatientRead,
    IncomingCrossTenantReferral,
    InterconsultCreate,
    InterconsultRead,
    InterconsultRespond,
    NetworkDoctor,
    OutgoingReferralRead,
    ReferralCreate,
    ReferralRead,
    ReferralUpdate,
)
from app.services._utils import new_uuid_bytes
from app.services.referral_service import accept_internal_transfer as svc_accept_internal_transfer
from app.services.referral_service import create_referral as svc_create_referral
from app.services.referral_service import update_referral as svc_update_referral

router = APIRouter(prefix="/api/v1/referrals", tags=["Referrals"], dependencies=[Depends(require_module("operaciones"))])

_RESERVED_DB_NAMES = {"salvio_control", "salvio_tenant_template"}


def _iter_tenant_ids() -> list[str]:
    """Enumera los tenants existentes escaneando las bases `salvio_*` -- no hay
    un catalogo central de tenants (cada uno vive en su propia base, ADR-01),
    asi que la busqueda de medicos en toda la red necesariamente escanea todas
    las bases de datos de tenant. Aceptable a esta escala; si la red crece
    mucho, esto se reemplaza por un indice en el plano de control."""
    server_url = make_url(DATABASE_URL).set(database=None).render_as_string(hide_password=False)
    admin_engine = create_engine(server_url, pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            rows = connection.execute(text("SHOW DATABASES LIKE 'salvio\\_%'")).fetchall()
        return [row[0].removeprefix("salvio_") for row in rows if row[0] not in _RESERVED_DB_NAMES]
    finally:
        admin_engine.dispose()


@router.post("/interconsults", response_model=InterconsultRead, status_code=status.HTTP_201_CREATED)
def create_interconsult(
    data: InterconsultCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    interconsult = Interconsult(**data_for_create(data, Interconsult, tenant_id=current_user.tenant_id))
    db.add(interconsult)
    db.flush()
    audit_mutation(db, request, current_user, action="create", table_name="interconsults", record_id=interconsult.id, new_values=model_to_dict(interconsult))
    commit_or_409(db)
    db.refresh(interconsult)
    return interconsult


@router.patch("/interconsults/{interconsult_id}/respond", response_model=InterconsultRead)
def respond_interconsult(
    interconsult_id: UUID,
    data: InterconsultRespond,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    interconsult = get_by_id_or_404(db, Interconsult, interconsult_id, current_user.tenant_id)
    old = model_to_dict(interconsult)
    interconsult.response = data.response
    interconsult.responded_at = data.responded_at or datetime.now(timezone.utc)
    interconsult.status = data.status
    audit_mutation(db, request, current_user, action="respond", table_name="interconsults", record_id=interconsult.id, old_values=old, new_values=model_to_dict(interconsult))
    commit_or_409(db)
    db.refresh(interconsult)
    return interconsult


@router.post("", response_model=ReferralRead, status_code=status.HTTP_201_CREATED)
def create_referral(
    data: ReferralCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    return svc_create_referral(db, current_user.tenant_id, data, current_user.id)


@router.get("/incoming", response_model=list[IncomingCrossTenantReferral])
def list_incoming_cross_tenant_referrals(current_user: User = Depends(get_current_user)):
    """Referencias cross_tenant dirigidas al tenant del usuario actual.

    Los `Referral` viven solo en la base del tenant que los crea (ADR-01);
    esta consulta lee el espejo del plano de control en vez de escanear todas
    las bases de tenant."""
    control_session: Session = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())()
    try:
        rows = (
            control_session.query(CrossTenantReferralIndex)
            .filter(CrossTenantReferralIndex.target_tenant_id == current_user.tenant_id)
            .order_by(CrossTenantReferralIndex.created_at.desc())
            .all()
        )
        return rows
    finally:
        control_session.close()


@router.get("/by-patient/{patient_id}", response_model=list[OutgoingReferralRead])
def list_referrals_by_patient(
    patient_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Referencias que este tenant ya envio para un paciente -- para que el
    medico que remite vea, sin salir del contexto de la consulta, a quien y
    donde ya lo remitio."""
    referrals = (
        db.query(Referral)
        .filter(Referral.patient_id == patient_id.bytes, Referral.tenant_id == current_user.tenant_id)
        .order_by(Referral.created_at.desc())
        .all()
    )
    tenant_name_cache: dict[str, str] = {}
    results: list[OutgoingReferralRead] = []
    for referral in referrals:
        target_tenant_name = None
        if referral.target_tenant_id:
            if referral.target_tenant_id not in tenant_name_cache:
                try:
                    target_session: Session = sessionmaker(autocommit=False, autoflush=False, bind=get_tenant_engine(referral.target_tenant_id))()
                    try:
                        target_tenant = target_session.query(Tenant).filter(Tenant.id == referral.target_tenant_id).first()
                        tenant_name_cache[referral.target_tenant_id] = target_tenant.name if target_tenant else referral.target_tenant_id
                    finally:
                        target_session.close()
                except Exception:
                    tenant_name_cache[referral.target_tenant_id] = referral.target_tenant_id
            target_tenant_name = tenant_name_cache[referral.target_tenant_id]
        results.append(
            OutgoingReferralRead(
                id=UUID(bytes=referral.id),
                referral_type=referral.referral_type,
                target_tenant_id=referral.target_tenant_id,
                target_tenant_name=target_tenant_name,
                target_doctor_name=referral.target_doctor_name,
                destination_area=referral.destination_area,
                transfer_reason=referral.transfer_reason,
                status=referral.status,
                created_at=referral.created_at,
            )
        )
    return results


@router.get("/network-doctors", response_model=list[NetworkDoctor])
def search_network_doctors(
    q: str = Query(min_length=2, max_length=100),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident, UserRole.clinic_admin)),
):
    """Busca medicos activos por nombre en toda la red Salvio (todas las
    clinicas), para poder referir a un colega sin conocer de antemano en que
    clinica atiende. Excluye el propio tenant (no tiene sentido referir a un
    colega de la misma clinica via este flujo de red)."""
    like_pattern = f"%{q.strip()}%"
    results: list[NetworkDoctor] = []
    for tenant_id in _iter_tenant_ids():
        if tenant_id == current_user.tenant_id:
            continue
        session: Session = sessionmaker(autocommit=False, autoflush=False, bind=get_tenant_engine(tenant_id))()
        try:
            tenant = session.query(Tenant).filter(Tenant.id == tenant_id).first()
            doctors = (
                session.query(User)
                .filter(
                    User.tenant_id == tenant_id,
                    User.role.in_([UserRole.doctor, UserRole.resident]),
                    User.is_active.is_(True),
                    User.deleted_at.is_(None),
                    User.full_name.ilike(like_pattern),
                )
                .limit(10)
                .all()
            )
            for doctor in doctors:
                results.append(
                    NetworkDoctor(
                        id=UUID(bytes=doctor.id),
                        full_name=doctor.full_name,
                        specialty=doctor.specialty,
                        tenant_id=tenant_id,
                        tenant_name=tenant.name if tenant else tenant_id,
                    )
                )
        except Exception:
            # Una base de tenant inalcanzable no debe tumbar la busqueda en
            # el resto de la red.
            continue
        finally:
            session.close()
    return results[:25]


@router.post("/cross-tenant/{referral_id}/import-patient", response_model=ImportedPatientRead)
def import_referred_patient(
    referral_id: UUID,
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident, UserRole.clinic_admin, UserRole.receptionist)),
):
    """Crea (o reutiliza) un registro local del paciente referido en la base
    del tenant destino, a partir de los datos minimos guardados en el indice
    del plano de control -- asi recepcion o el medico destino pueden
    agendarle una cita sin tener acceso a la base de origen."""
    control_session: Session = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())()
    try:
        index_row = (
            control_session.query(CrossTenantReferralIndex)
            .filter(CrossTenantReferralIndex.referral_id == referral_id.bytes)
            .first()
        )
        if index_row is None or index_row.target_tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referencia no encontrada.")

        if index_row.imported_patient_id:
            return ImportedPatientRead(patient_id=UUID(bytes=index_row.imported_patient_id), already_existed=True)

        if not index_row.patient_dob or not index_row.patient_gender:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La referencia no tiene fecha de nacimiento o genero del paciente -- no se puede crear el registro local.",
            )

        dest_session: Session = sessionmaker(autocommit=False, autoflush=False, bind=get_tenant_engine(current_user.tenant_id))()
        try:
            # La identidad real de la persona es el DUI, no la referencia --
            # si ya se importo antes (desde otra referencia, u otra vez con
            # la misma) se reutiliza el mismo paciente local en vez de crear
            # un duplicado. Sin esto, cada referencia nueva del mismo
            # paciente generaba su propio registro.
            existing_patient = None
            if index_row.patient_dui:
                existing_patient = (
                    dest_session.query(Patient)
                    .filter(Patient.tenant_id == current_user.tenant_id, Patient.dui == index_row.patient_dui)
                    .first()
                )

            if existing_patient is not None:
                new_patient_id = existing_patient.id
                already_existed = True
            else:
                name_parts = index_row.patient_name.strip().split(" ", 1)
                first_name = name_parts[0] if name_parts else index_row.patient_name
                last_name = name_parts[1] if len(name_parts) > 1 else "-"
                try:
                    insurance_type = InsuranceType(index_row.patient_insurance_type) if index_row.patient_insurance_type else InsuranceType.ninguno
                except ValueError:
                    insurance_type = InsuranceType.ninguno
                new_patient = Patient(
                    id=new_uuid_bytes(),
                    tenant_id=current_user.tenant_id,
                    medical_record_number=f"REF-{uuid4().hex[:10].upper()}",
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=index_row.patient_dob,
                    gender=Gender(index_row.patient_gender),
                    dui=index_row.patient_dui,
                    nit=index_row.patient_nit,
                    email=index_row.patient_email,
                    phone=index_row.patient_phone,
                    address=index_row.patient_address,
                    emergency_contact_name=index_row.patient_emergency_contact_name,
                    emergency_contact_phone=index_row.patient_emergency_contact_phone,
                    emergency_contact_relationship=index_row.patient_emergency_contact_relationship,
                    insurance_type=insurance_type,
                    insurance_number=index_row.patient_insurance_number,
                    is_referred=True,
                )
                dest_session.add(new_patient)
                dest_session.commit()
                new_patient_id = new_patient.id
                already_existed = False
        finally:
            dest_session.close()

        index_row.imported_patient_id = new_patient_id
        control_session.commit()
        return ImportedPatientRead(patient_id=UUID(bytes=new_patient_id), already_existed=already_existed)
    finally:
        control_session.close()


_CROSS_TENANT_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"accepted", "rejected"},
    "accepted": {"completed"},
    "completed": set(),
    "rejected": set(),
}


@router.patch("/cross-tenant/{referral_id}/status", response_model=IncomingCrossTenantReferral)
def update_cross_tenant_referral_status(
    referral_id: UUID,
    data: CrossTenantReferralStatusUpdate,
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    """El medico destino marca si sigue en control con el paciente
    ('accepted') o le da de alta ('completed'). El `Referral` real vive en la
    base del tenant de origen (ADR-01), asi que se actualiza ahi via
    get_tenant_engine y se refleja el nuevo estado en el indice del plano de
    control para que el lado que remitio pueda verlo."""
    control_session: Session = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())()
    try:
        index_row = (
            control_session.query(CrossTenantReferralIndex)
            .filter(CrossTenantReferralIndex.referral_id == referral_id.bytes)
            .first()
        )
        if index_row is None or index_row.target_tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referencia no encontrada.")

        allowed = _CROSS_TENANT_STATUS_TRANSITIONS.get(index_row.status, set())
        if data.status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No se puede pasar la referencia de '{index_row.status}' a '{data.status}'",
            )

        source_session: Session = sessionmaker(autocommit=False, autoflush=False, bind=get_tenant_engine(index_row.source_tenant_id))()
        try:
            referral = (
                source_session.query(Referral)
                .filter(Referral.id == index_row.referral_id, Referral.tenant_id == index_row.source_tenant_id)
                .first()
            )
            if referral is not None:
                referral.status = ReferralStatus(data.status)
                source_session.commit()
        finally:
            source_session.close()

        index_row.status = data.status
        control_session.commit()
        control_session.refresh(index_row)
        return IncomingCrossTenantReferral.model_validate(index_row)
    finally:
        control_session.close()


@router.get("/cross-tenant/{referral_id}/history", response_model=CrossTenantHistoryRead)
def get_cross_tenant_history(
    referral_id: UUID,
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident, UserRole.clinic_admin)),
):
    """Historial clinico completo del paciente referido, leido en vivo desde
    la base del tenant de origen. Solo accesible por el tenant destino de la
    referencia (validado contra el indice del plano de control)."""
    control_session: Session = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())()
    try:
        index_row = (
            control_session.query(CrossTenantReferralIndex)
            .filter(CrossTenantReferralIndex.referral_id == referral_id.bytes)
            .first()
        )
    finally:
        control_session.close()

    if index_row is None or index_row.target_tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referencia no encontrada.")

    return _build_cross_tenant_history(index_row)


@router.get("/imported-patient/{patient_id}/history", response_model=CrossTenantHistoryRead)
def get_imported_patient_history(
    patient_id: UUID,
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident, UserRole.clinic_admin)),
):
    """Igual que /cross-tenant/{referral_id}/history, pero buscado desde el
    lado del paciente local ya importado (ver POST .../import-patient) -- asi
    su perfil en este tenant tambien puede mostrar la linea de tiempo de
    diagnosticos de la clinica de origen, no solo un perfil vacio."""
    control_session: Session = sessionmaker(autocommit=False, autoflush=False, bind=get_control_engine())()
    try:
        index_row = (
            control_session.query(CrossTenantReferralIndex)
            .filter(
                CrossTenantReferralIndex.imported_patient_id == patient_id.bytes,
                CrossTenantReferralIndex.target_tenant_id == current_user.tenant_id,
            )
            .first()
        )
    finally:
        control_session.close()

    if index_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Este paciente no proviene de una referencia.")

    return _build_cross_tenant_history(index_row)


def _build_cross_tenant_history(index_row: CrossTenantReferralIndex) -> CrossTenantHistoryRead:
    source_session: Session = sessionmaker(autocommit=False, autoflush=False, bind=get_tenant_engine(index_row.source_tenant_id))()
    try:
        patient = (
            source_session.query(Patient)
            .filter(Patient.id == index_row.patient_id, Patient.tenant_id == index_row.source_tenant_id)
            .first()
        )
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente referido no encontrado.")

        source_tenant = source_session.query(Tenant).filter(Tenant.id == index_row.source_tenant_id).first()

        encounters = (
            source_session.query(Encounter)
            .filter(Encounter.patient_id == index_row.patient_id, Encounter.tenant_id == index_row.source_tenant_id)
            .order_by(Encounter.started_at.asc())
            .all()
        )
        encounter_summaries: list[CrossTenantEncounterSummary] = []
        for encounter in encounters:
            doctor = source_session.query(User).filter(User.id == encounter.doctor_id).first()
            notes = (
                source_session.query(ClinicalNote)
                .filter(ClinicalNote.encounter_id == encounter.id, ClinicalNote.tenant_id == index_row.source_tenant_id)
                .order_by(ClinicalNote.created_at.asc())
                .all()
            )
            diagnoses = (
                source_session.query(RecordDiagnosis)
                .filter(RecordDiagnosis.encounter_id == encounter.id, RecordDiagnosis.tenant_id == index_row.source_tenant_id)
                .all()
            )
            encounter_summaries.append(
                CrossTenantEncounterSummary(
                    id=UUID(bytes=encounter.id),
                    doctor_name=doctor.full_name if doctor else None,
                    chief_complaint=encounter.chief_complaint,
                    status=encounter.status.value if hasattr(encounter.status, "value") else str(encounter.status),
                    started_at=encounter.started_at,
                    closed_at=encounter.closed_at,
                    notes=[
                        CrossTenantEncounterNote(
                            note_type=note.note_type.value if hasattr(note.note_type, "value") else str(note.note_type),
                            content=note.content,
                            authored_by_name=note.authored_by_name,
                            is_closed=note.is_closed,
                            created_at=note.created_at,
                        )
                        for note in notes
                    ],
                    diagnoses=[
                        CrossTenantEncounterDiagnosis(
                            code=diagnosis.cie10_code,
                            description=diagnosis.cie10_description,
                            classification="primary" if diagnosis.is_primary_diagnosis else "background" if diagnosis.is_background else "secondary",
                            severity=diagnosis.severity.value if diagnosis.severity else None,
                        )
                        for diagnosis in diagnoses
                    ],
                )
            )

        return CrossTenantHistoryRead(
            source_tenant_id=index_row.source_tenant_id,
            source_tenant_name=source_tenant.name if source_tenant else index_row.source_tenant_id,
            referral=IncomingCrossTenantReferral.model_validate(index_row),
            patient=CrossTenantPatientSummary(
                id=UUID(bytes=patient.id),
                full_name=f"{patient.first_name} {patient.last_name}".strip(),
                date_of_birth=patient.date_of_birth,
                gender=patient.gender.value if hasattr(patient.gender, "value") else str(patient.gender),
                dui=patient.dui,
            ),
            encounters=encounter_summaries,
        )
    finally:
        source_session.close()


@router.get("/{referral_id}", response_model=ReferralRead)
def get_referral(referral_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_by_id_or_404(db, Referral, referral_id, current_user.tenant_id)


@router.patch("/{referral_id}", response_model=ReferralRead)
def update_referral(
    referral_id: UUID,
    data: ReferralUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    return svc_update_referral(db, referral_id.bytes, current_user.tenant_id, data, current_user.id)


@router.post("/{referral_id}/accept-internal-transfer", response_model=ReferralRead)
def accept_internal_transfer(
    referral_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.doctor, UserRole.resident)),
):
    return svc_accept_internal_transfer(db, referral_id.bytes, current_user.tenant_id, current_user.id)
