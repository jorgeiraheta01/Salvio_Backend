"""Aplicacion real (a nivel de API) del interruptor "Inactivar modulo" del
panel del dueno -- antes solo existia como gate del lado del frontend
(Salvio-frontend/src/shared/components/module-gate-boundary.tsx), asi que
un usuario de clinica que llamara la API directamente podia seguir usando
un modulo que el dueno habia apagado. Misma convencion "sin fila =
habilitado" que app/modules/tenants/service.py:list_tenant_modules().

`db` se toma de Depends(get_db), la misma sesion que cada endpoint ya abre
y que get_db() ya resuelve contra la BD del tenant correcto via el claim
`tenant_id` del JWT -- no hace falta abrir una conexion nueva como si hace
el patron cross-tenant del panel del dueno (list_tenant_modules abre una
conexion descartable porque el dueno puede pedir el estado de CUALQUIER
tenant, no del suyo propio)."""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.models.tenant import TenantModuleFlag, User


def require_module(module_key: str):
    def _dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> None:
        flag = (
            db.query(TenantModuleFlag)
            .filter(TenantModuleFlag.tenant_id == current_user.tenant_id, TenantModuleFlag.module_key == module_key)
            .first()
        )
        if flag is not None and not flag.enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Module '{module_key}' is disabled for this clinic.")

    return _dependency
