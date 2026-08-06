
CREATE TABLE audit_log (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	tenant_id VARCHAR(50), 
	user_id BINARY(16), 
	action VARCHAR(50) NOT NULL, 
	table_name VARCHAR(100) NOT NULL, 
	record_id BINARY(16), 
	old_values JSON, 
	new_values JSON, 
	ip_address VARCHAR(45), 
	user_agent TEXT, 
	created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
)

;


CREATE TABLE clinical_systems_catalog (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	system_name VARCHAR(100) NOT NULL, 
	applies_to SET('exam','review') NOT NULL, 
	sort_order TINYINT NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (system_name)
)

;


CREATE TABLE development_milestones_config (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	milestone_name VARCHAR(255) NOT NULL, 
	category ENUM('motor_gross','motor_fine','communication_language','cognitive','social_emotional') NOT NULL, 
	age_median_months NUMERIC(5, 1) NOT NULL, 
	alert_age_months NUMERIC(5, 1) NOT NULL, 
	description TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id)
)

;


CREATE TABLE lab_tests_catalog (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	test_code VARCHAR(20) NOT NULL, 
	test_name VARCHAR(255) NOT NULL, 
	category VARCHAR(100), 
	unit VARCHAR(50), 
	ref_range VARCHAR(100), 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (test_code)
)

;


CREATE TABLE tenants (
	id VARCHAR(50) NOT NULL,
	name VARCHAR(255) NOT NULL,
	country VARCHAR(2) NOT NULL,
	status ENUM('active','suspended','archived') NOT NULL,
	created_at DATETIME NOT NULL DEFAULT now(),
	updated_at DATETIME NOT NULL DEFAULT now(),
	PRIMARY KEY (id)
)

;


CREATE TABLE facilities (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	tenant_id VARCHAR(50) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	facility_type VARCHAR(100), 
	phone VARCHAR(30), 
	email VARCHAR(255), 
	address TEXT, 
	is_active BOOL NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE hc_templates (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	tenant_id VARCHAR(50) NOT NULL, 
	specialty VARCHAR(100) NOT NULL, 
	require_insurance_affiliation BOOL NOT NULL, 
	require_labor_data BOOL NOT NULL, 
	require_attention_number BOOL NOT NULL, 
	show_glasgow_scale BOOL NOT NULL, 
	show_triage BOOL NOT NULL, 
	show_pediatric_perinatal BOOL NOT NULL, 
	show_clinical_scales BOOL NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE medication_catalog (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	tenant_id VARCHAR(50), 
	medication_code VARCHAR(50), 
	generic_name VARCHAR(255) NOT NULL, 
	brand_name VARCHAR(255), 
	concentration VARCHAR(100), 
	pharmaceutical_form VARCHAR(100), 
	route VARCHAR(100), 
	is_controlled BOOL NOT NULL, 
	is_active BOOL NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE patients (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	tenant_id VARCHAR(50) NOT NULL, 
	medical_record_number VARCHAR(50) NOT NULL, 
	first_name VARCHAR(100) NOT NULL, 
	last_name VARCHAR(100) NOT NULL, 
	date_of_birth DATE NOT NULL, 
	gender ENUM('male','female','other') NOT NULL, 
	dui VARCHAR(10), 
	nit VARCHAR(20), 
	email VARCHAR(255), 
	phone VARCHAR(30), 
	address TEXT, 
	emergency_contact_name VARCHAR(255), 
	emergency_contact_phone VARCHAR(30), 
	emergency_contact_relationship VARCHAR(100), 
	insurance_type ENUM('particular','ss_pensionado','ss_cotizante','ss_beneficiario','red_publica','privado','ninguno','otro') NOT NULL, 
	insurance_number VARCHAR(50), 
	attention_number VARCHAR(50), 
	last_employer VARCHAR(255), 
	work_phone VARCHAR(30), 
	last_occupation VARCHAR(200), 
	last_contribution_period VARCHAR(50), 
	last_work_date DATE, 
	deleted_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE users (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	tenant_id VARCHAR(50) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	hashed_password VARCHAR(255) NOT NULL, 
	full_name VARCHAR(255) NOT NULL, 
	`role` ENUM('super_admin','clinic_admin','doctor','resident','nurse','receptionist','accountant','patient') NOT NULL, 
	is_active BOOL NOT NULL, 
	deleted_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	UNIQUE (email)
)

;


CREATE TABLE appointments (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	doctor_id BINARY(16) NOT NULL, 
	scheduled_at DATETIME NOT NULL, 
	appointment_type VARCHAR(100), 
	status ENUM('scheduled','confirmed','checked_in','in_consultation','completed','cancelled','no_show','rescheduled') NOT NULL, 
	notes TEXT, 
	deleted_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(doctor_id) REFERENCES users (id) ON DELETE RESTRICT
)

;


CREATE TABLE departments (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	tenant_id VARCHAR(50) NOT NULL, 
	facility_id BINARY(16), 
	name VARCHAR(255) NOT NULL, 
	specialty VARCHAR(100), 
	is_clinical BOOL NOT NULL, 
	is_active BOOL NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(facility_id) REFERENCES facilities (id) ON DELETE SET NULL
)

;


CREATE TABLE medication_inventory (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	tenant_id VARCHAR(50) NOT NULL, 
	medication_id BINARY(16) NOT NULL, 
	facility_id BINARY(16), 
	lot_number VARCHAR(100), 
	expiration_date DATE, 
	quantity_on_hand DECIMAL(12, 2) NOT NULL, 
	minimum_stock DECIMAL(12, 2) NOT NULL, 
	unit VARCHAR(50), 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(medication_id) REFERENCES medication_catalog (id) ON DELETE RESTRICT, 
	FOREIGN KEY(facility_id) REFERENCES facilities (id) ON DELETE SET NULL
)

;


CREATE TABLE otp_tokens_sms (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	user_id BINARY(16) NOT NULL, 
	phone_number VARCHAR(30) NOT NULL, 
	otp_code_hash VARCHAR(64) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	used BOOL NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;


CREATE TABLE patient_admissions (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	admission_datetime DATETIME NOT NULL, 
	discharge_datetime DATETIME, 
	service VARCHAR(100), 
	bed_number VARCHAR(20), 
	admitting_doctor BINARY(16), 
	admitting_doctor_name VARCHAR(255), 
	diagnosis_on_admission TEXT, 
	discharge_diagnosis_cie10 VARCHAR(10), 
	status ENUM('active','discharged','transferred') NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(admitting_doctor) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE patient_allergies (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	allergen VARCHAR(255) NOT NULL, 
	reaction VARCHAR(255), 
	severity ENUM('mild','moderate','severe','life_threatening') NOT NULL, 
	notes TEXT, 
	is_active BOOL NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE patient_chronic_diseases (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	disease_name VARCHAR(255) NOT NULL, 
	cie10_code VARCHAR(10), 
	diagnosis_date DATE, 
	is_active BOOL NOT NULL, 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE patient_consents (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	consent_type ENUM('treatment','surgery','anesthesia','data','whatsapp') NOT NULL, 
	consent_text TEXT NOT NULL, 
	signed_at DATETIME NOT NULL DEFAULT now(), 
	signed_by BINARY(16), 
	pdf_url VARCHAR(500), 
	revoked_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(signed_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE patient_development_hx (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	walking_age_months DECIMAL(5, 1), 
	first_words_age_months DECIMAL(5, 1), 
	toilet_training_age_months DECIMAL(5, 1), 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (patient_id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE patient_development_records (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	milestone_id BINARY(16) NOT NULL, 
	achieved_at DATE, 
	delay_alert BOOL NOT NULL, 
	recorded_by BINARY(16), 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(milestone_id) REFERENCES development_milestones_config (id) ON DELETE RESTRICT, 
	FOREIGN KEY(recorded_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE patient_family_hx (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	relationship VARCHAR(100), 
	condition_name VARCHAR(255), 
	cie10_code VARCHAR(10), 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE patient_gynecological_hx (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	menarche_age TINYINT, 
	last_menstrual_period DATE, 
	pregnancies TINYINT, 
	deliveries TINYINT, 
	abortions TINYINT, 
	contraceptive_method VARCHAR(255), 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (patient_id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE patient_hospitalizations_hx (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	admission_date DATE NOT NULL, 
	discharge_date DATE, 
	reason TEXT, 
	hospital VARCHAR(255), 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE patient_immunizations (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	vaccine_name VARCHAR(255) NOT NULL, 
	dose_number VARCHAR(50), 
	lot_number VARCHAR(100), 
	applied_at DATE, 
	next_due_at DATE, 
	applied_by BINARY(16), 
	status ENUM('applied','pending','refused','contraindicated') NOT NULL, 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(applied_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE patient_medications (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	medication_name VARCHAR(255) NOT NULL, 
	dose VARCHAR(100), 
	frequency VARCHAR(100), 
	start_date DATE, 
	end_date DATE, 
	is_active BOOL NOT NULL, 
	prescribed_by BINARY(16), 
	prescribed_by_name VARCHAR(255), 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(prescribed_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE patient_perinatal_hx (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	gestational_weeks TINYINT, 
	prenatal_controls TINYINT, 
	delivery_route ENUM('vaginal','cesarean','forceps'), 
	birth_weight DECIMAL(6, 2), 
	birth_length DECIMAL(5, 1), 
	head_circumference DECIMAL(5, 1), 
	apgar_1min TINYINT, 
	apgar_5min TINYINT, 
	apgar_10min TINYINT, 
	ballard_weeks TINYINT, 
	silverman_retractions TINYINT, 
	silverman_cyanosis TINYINT, 
	silverman_grunting TINYINT, 
	silverman_breathing TINYINT, 
	silverman_auscultation TINYINT, 
	silverman_total TINYINT, 
	nicu_admission BOOL, 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (patient_id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE patient_physiological_hx (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	blood_type VARCHAR(5), 
	rh_factor ENUM('positive','negative','unknown'), 
	smoking ENUM('never','former','current') NOT NULL, 
	alcohol ENUM('never','occasional','daily') NOT NULL, 
	drugs TEXT, 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (patient_id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE patient_social_hx (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	occupation VARCHAR(255), 
	living_conditions TEXT, 
	housing_type VARCHAR(100), 
	has_water BOOL, 
	has_sewer BOOL, 
	has_electricity BOOL, 
	pets TEXT, 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (patient_id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE patient_surgeries (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	surgery_name VARCHAR(255) NOT NULL, 
	surgery_date DATE, 
	hospital VARCHAR(255), 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE revoked_tokens (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	jti VARCHAR(255) NOT NULL, 
	user_id BINARY(16) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (jti), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;


CREATE TABLE billing (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	appointment_id BINARY(16), 
	amount DECIMAL(10, 2) NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	status ENUM('pending','paid','void','refunded') NOT NULL, 
	payment_method VARCHAR(50), 
	payment_date DATETIME, 
	invoice_number VARCHAR(50), 
	void_reason TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id) ON DELETE SET NULL
)

;


CREATE TABLE clinical_records (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	appointment_id BINARY(16), 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	doctor_id BINARY(16) NOT NULL, 
	doctor_name VARCHAR(255) NOT NULL, 
	status ENUM('draft','signed') NOT NULL, 
	soap_subjective TEXT, 
	soap_objective TEXT, 
	soap_assessment TEXT, 
	soap_plan TEXT, 
	informant VARCHAR(255), 
	informant_relationship VARCHAR(100), 
	visit_number SMALLINT, 
	printed_at DATETIME, 
	signed_at DATETIME, 
	digital_signature TEXT, 
	deleted_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id) ON DELETE SET NULL, 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(doctor_id) REFERENCES users (id) ON DELETE RESTRICT
)

;


CREATE TABLE rooms (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	tenant_id VARCHAR(50) NOT NULL, 
	facility_id BINARY(16), 
	department_id BINARY(16), 
	room_number VARCHAR(50) NOT NULL, 
	room_type VARCHAR(100), 
	floor VARCHAR(50), 
	is_active BOOL NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(facility_id) REFERENCES facilities (id) ON DELETE SET NULL, 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL
)

;


CREATE TABLE triage_records (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	appointment_id BINARY(16), 
	admission_id BINARY(16), 
	received_at DATETIME NOT NULL, 
	triage_at DATETIME, 
	nursing_prep_at DATETIME, 
	priority ENUM('low','moderate','high','critical') NOT NULL, 
	area VARCHAR(100), 
	systolic_bp SMALLINT, 
	diastolic_bp SMALLINT, 
	heart_rate SMALLINT, 
	resp_rate TINYINT, 
	temperature DECIMAL(4, 1), 
	spo2 TINYINT, 
	glasgow_total TINYINT, 
	chief_complaint TEXT, 
	created_by BINARY(16), 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id) ON DELETE SET NULL, 
	FOREIGN KEY(admission_id) REFERENCES patient_admissions (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE wa_messages (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	appointment_id BINARY(16), 
	message_type VARCHAR(50), 
	template_name VARCHAR(100), 
	status ENUM('pending','sent','failed','delivered','read') NOT NULL, 
	error_message TEXT, 
	sent_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id) ON DELETE SET NULL
)

;


CREATE TABLE beds (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	tenant_id VARCHAR(50) NOT NULL, 
	room_id BINARY(16), 
	bed_number VARCHAR(50) NOT NULL, 
	status ENUM('available','occupied','cleaning','maintenance','blocked') NOT NULL, 
	current_admission_id BINARY(16), 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(room_id) REFERENCES rooms (id) ON DELETE SET NULL, 
	FOREIGN KEY(current_admission_id) REFERENCES patient_admissions (id) ON DELETE SET NULL
)

;


CREATE TABLE billing_items (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	billing_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	item_type VARCHAR(100), 
	description VARCHAR(255) NOT NULL, 
	quantity DECIMAL(10, 2) NOT NULL, 
	unit_price DECIMAL(10, 2) NOT NULL, 
	discount_amount DECIMAL(10, 2) NOT NULL, 
	tax_amount DECIMAL(10, 2) NOT NULL, 
	total_amount DECIMAL(10, 2) NOT NULL, 
	service_date DATETIME, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(billing_id) REFERENCES billing (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE clinical_notes (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	admission_id BINARY(16), 
	clinical_record_id BINARY(16), 
	note_type ENUM('progress','nursing','discharge','other') NOT NULL, 
	content TEXT NOT NULL, 
	authored_by BINARY(16), 
	authored_by_name VARCHAR(255), 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(admission_id) REFERENCES patient_admissions (id) ON DELETE SET NULL, 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(authored_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE clinical_problems (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	clinical_record_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	problem_name VARCHAR(255) NOT NULL, 
	is_active BOOL NOT NULL, 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE clinical_procedures (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	clinical_record_id BINARY(16), 
	consent_id BINARY(16), 
	procedure_name VARCHAR(255) NOT NULL, 
	performed_by BINARY(16), 
	performed_by_name VARCHAR(255), 
	performed_at DATETIME, 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(consent_id) REFERENCES patient_consents (id) ON DELETE SET NULL, 
	FOREIGN KEY(performed_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE clinical_scale_results (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	clinical_record_id BINARY(16), 
	scale_name ENUM('barthel','braden','morse','asa','silverman','flacc','eva') NOT NULL, 
	total_score SMALLINT, 
	risk_level VARCHAR(50), 
	details JSON, 
	performed_by BINARY(16), 
	performed_at DATETIME NOT NULL DEFAULT now(), 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(performed_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE imaging_studies (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	clinical_record_id BINARY(16), 
	study_type VARCHAR(100) NOT NULL, 
	body_part VARCHAR(100), 
	ordered_by BINARY(16), 
	order_datetime DATETIME NOT NULL DEFAULT now(), 
	performed_at DATETIME, 
	result_summary TEXT, 
	pdf_url VARCHAR(500), 
	dicom_url VARCHAR(500), 
	status ENUM('ordered','performed','reviewed','cancelled') NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(ordered_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE interconsults (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	clinical_record_id BINARY(16), 
	requesting_doctor BINARY(16) NOT NULL, 
	requesting_doctor_name VARCHAR(255) NOT NULL, 
	consulting_specialty VARCHAR(100) NOT NULL, 
	reason TEXT, 
	requested_at DATETIME NOT NULL DEFAULT now(), 
	response TEXT, 
	responded_at DATETIME, 
	status ENUM('pending','accepted','completed','rejected') NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(requesting_doctor) REFERENCES users (id) ON DELETE RESTRICT
)

;


CREATE TABLE lab_orders (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	clinical_record_id BINARY(16), 
	ordered_by BINARY(16) NOT NULL, 
	lab_test_id BINARY(16), 
	test_name VARCHAR(255) NOT NULL, 
	order_datetime DATETIME NOT NULL DEFAULT now(), 
	status ENUM('ordered','collected','processing','completed','cancelled') NOT NULL, 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(ordered_by) REFERENCES users (id) ON DELETE RESTRICT, 
	FOREIGN KEY(lab_test_id) REFERENCES lab_tests_catalog (id) ON DELETE SET NULL
)

;


CREATE TABLE patient_documents (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	clinical_record_id BINARY(16), 
	category ENUM('identity','consent','clinical','lab','imaging','billing','referral','other') NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	file_url VARCHAR(500) NOT NULL, 
	file_name VARCHAR(255), 
	mime_type VARCHAR(100), 
	checksum VARCHAR(128), 
	uploaded_by BINARY(16), 
	is_confidential BOOL NOT NULL, 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE patient_growth_measurements (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	clinical_record_id BINARY(16), 
	measured_at DATETIME NOT NULL DEFAULT now(), 
	weight DECIMAL(6, 2), 
	height DECIMAL(5, 1), 
	head_circumference DECIMAL(5, 1), 
	bmi DECIMAL(5, 2), 
	weight_percentile DECIMAL(5, 2), 
	height_percentile DECIMAL(5, 2), 
	bmi_percentile DECIMAL(5, 2), 
	recorded_by BINARY(16), 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(recorded_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE payments (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	billing_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	amount DECIMAL(10, 2) NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	payment_method VARCHAR(50) NOT NULL, 
	reference_number VARCHAR(100), 
	status ENUM('pending','completed','failed','refunded','void') NOT NULL, 
	paid_at DATETIME, 
	processed_by BINARY(16), 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(billing_id) REFERENCES billing (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(processed_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE physical_exam_findings (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	clinical_record_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	system_name VARCHAR(100) NOT NULL, 
	is_normal BOOL, 
	findings TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE prescriptions (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	clinical_record_id BINARY(16), 
	prescribed_by BINARY(16) NOT NULL, 
	prescribed_by_name VARCHAR(255) NOT NULL, 
	prescribed_at DATETIME NOT NULL DEFAULT now(), 
	pdf_url VARCHAR(500), 
	status ENUM('pending_override','active','dispensed','cancelled') NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(prescribed_by) REFERENCES users (id) ON DELETE RESTRICT
)

;


CREATE TABLE record_plans (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	clinical_record_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	plan_type VARCHAR(100), 
	description TEXT, 
	due_date DATE, 
	completed_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE referrals (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	clinical_record_id BINARY(16), 
	referral_type ENUM('internal','internal_transfer','cross_tenant','public') NOT NULL, 
	source_service VARCHAR(100), 
	destination_area VARCHAR(100), 
	transfer_reason TEXT, 
	referred_by BINARY(16), 
	referred_by_name VARCHAR(255), 
	target_tenant_id VARCHAR(50), 
	status ENUM('pending','accepted','completed','rejected') NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(referred_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE review_of_systems (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	clinical_record_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	system_name VARCHAR(100) NOT NULL, 
	is_positive BOOL, 
	comments TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE vital_signs (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	patient_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	clinical_record_id BINARY(16), 
	recorded_at DATETIME NOT NULL DEFAULT now(), 
	bp_systolic SMALLINT, 
	bp_diastolic SMALLINT, 
	heart_rate SMALLINT, 
	resp_rate TINYINT, 
	temperature DECIMAL(4, 1), 
	spo2 TINYINT, 
	fio2 TINYINT, 
	glucometria SMALLINT, 
	weight DECIMAL(6, 2), 
	height DECIMAL(5, 1), 
	pain_scale_eva TINYINT, 
	glasgow_ocular TINYINT, 
	glasgow_verbal TINYINT, 
	glasgow_motor TINYINT, 
	glasgow_total TINYINT, 
	perimetro_cefalico DECIMAL(4, 1), 
	flacc TINYINT, 
	recorded_by BINARY(16), 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(recorded_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE imaging_attachments (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	imaging_study_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	file_url VARCHAR(500) NOT NULL, 
	file_type VARCHAR(100), 
	description VARCHAR(255), 
	uploaded_by BINARY(16), 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(imaging_study_id) REFERENCES imaging_studies (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE imaging_reports (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	imaging_study_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	radiologist_id BINARY(16), 
	radiologist_name VARCHAR(255), 
	findings TEXT, 
	impression TEXT, 
	recommendations TEXT, 
	signed_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(imaging_study_id) REFERENCES imaging_studies (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(radiologist_id) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE lab_order_items (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	lab_order_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	lab_test_id BINARY(16), 
	test_code VARCHAR(20), 
	test_name VARCHAR(255) NOT NULL, 
	specimen_type VARCHAR(100), 
	status ENUM('ordered','collected','processing','completed','cancelled') NOT NULL, 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(lab_order_id) REFERENCES lab_orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(lab_test_id) REFERENCES lab_tests_catalog (id) ON DELETE SET NULL
)

;


CREATE TABLE lab_specimens (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	lab_order_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	specimen_type VARCHAR(100) NOT NULL, 
	barcode VARCHAR(100), 
	collected_by BINARY(16), 
	collected_at DATETIME, 
	received_at DATETIME, 
	rejection_reason TEXT, 
	status ENUM('pending','collected','rejected','received') NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(lab_order_id) REFERENCES lab_orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(collected_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE prescription_items (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	prescription_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	medication_name VARCHAR(255) NOT NULL, 
	medication_code VARCHAR(50), 
	concentration VARCHAR(100), 
	pharmaceutical_form VARCHAR(100), 
	dose VARCHAR(100), 
	frequency VARCHAR(100), 
	duration VARCHAR(100), 
	route VARCHAR(100), 
	quantity DECIMAL(10, 2), 
	refills SMALLINT NOT NULL, 
	start_date DATE, 
	end_date DATE, 
	indication VARCHAR(255), 
	instructions TEXT, 
	status ENUM('active','suspended','completed','substituted') NOT NULL, 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(prescription_id) REFERENCES prescriptions (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE public_access_tokens (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	referral_id BINARY(16), 
	patient_id BINARY(16) NOT NULL, 
	clinical_record_id BINARY(16) NOT NULL, 
	token VARCHAR(255) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(referral_id) REFERENCES referrals (id) ON DELETE CASCADE, 
	FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE, 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE CASCADE, 
	UNIQUE (token)
)

;


CREATE TABLE record_diagnoses (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	clinical_record_id BINARY(16) NOT NULL, 
	tenant_id VARCHAR(50) NOT NULL, 
	clinical_problem_id BINARY(16), 
	cie10_code VARCHAR(10) NOT NULL, 
	cie10_description VARCHAR(255) NOT NULL, 
	diagnosis_type ENUM('presumptive','definitive','ruled_out') NOT NULL, 
	is_first_time BOOL NOT NULL, 
	is_primary_diagnosis BOOL NOT NULL, 
	is_background BOOL NOT NULL, 
	is_outpatient BOOL NOT NULL, 
	notes TEXT, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(clinical_record_id) REFERENCES clinical_records (id) ON DELETE CASCADE, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(clinical_problem_id) REFERENCES clinical_problems (id) ON DELETE SET NULL
)

;


CREATE TABLE lab_results (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	lab_order_id BINARY(16) NOT NULL, 
	lab_order_item_id BINARY(16), 
	tenant_id VARCHAR(50) NOT NULL, 
	analyte_name VARCHAR(255), 
	result_value VARCHAR(255), 
	numeric_value DECIMAL(12, 4), 
	unit VARCHAR(50), 
	reference_range VARCHAR(255), 
	is_abnormal BOOL, 
	abnormal_flag VARCHAR(20), 
	pdf_url VARCHAR(500), 
	resulted_at DATETIME, 
	verified_by BINARY(16), 
	verified_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(lab_order_id) REFERENCES lab_orders (id) ON DELETE RESTRICT, 
	FOREIGN KEY(lab_order_item_id) REFERENCES lab_order_items (id) ON DELETE SET NULL, 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(verified_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE medication_inventory_movements (
	id BINARY(16) NOT NULL DEFAULT 'UUID_TO_BIN(UUID())', 
	tenant_id VARCHAR(50) NOT NULL, 
	inventory_id BINARY(16) NOT NULL, 
	prescription_item_id BINARY(16), 
	movement_type ENUM('purchase','dispensing','adjustment','transfer','return_in','waste') NOT NULL, 
	quantity DECIMAL(12, 2) NOT NULL, 
	reference VARCHAR(255), 
	notes TEXT, 
	created_by BINARY(16), 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(inventory_id) REFERENCES medication_inventory (id) ON DELETE CASCADE, 
	FOREIGN KEY(prescription_item_id) REFERENCES prescription_items (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
)

;

