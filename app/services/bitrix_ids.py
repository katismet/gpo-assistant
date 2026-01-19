# Entity Type IDs (используем реальные entityTypeId из Bitrix24)
OBJECT_ETID = 1046   # Объект (смарт-процесс)
SHIFT_ETID = 1050    # Смены
RESOURCE_ETID = 1056  # Ресурс
TIMESHEET_ETID = 1060  # Табель

# Object fields (entityTypeId = 1046, смарт-процесс)
UF_OBJECT_ADDRESS = "ufCrm5UfCrmObjectAddress"  # Пользовательское поле адреса
UF_OBJECT_CODE = "ufCrm5UfCrmObjectCode"  # Пользовательское поле кода
UF_OBJECT_OWNER = "ufCrm5UfCrmObjectOwner"  # Пользовательское поле ответственного

# Shift fields (entityTypeId = 1050)
UF_DATE = "ufCrm7UfCrmDate"
UF_TYPE = "ufCrm7UfCrmShiftType"
UF_OBJECT_LINK = "ufCrm7UfCrmObject"   # поле в Смене, тип «Привязка к элементам CRM», разрешить сущность «Объект (ID=1046)»
UF_PLAN_TOTAL = "ufCrm7UfCrmPlanTotal"
UF_FACT_TOTAL = "ufCrm7UfCrmFactTotal"
UF_EFF_RAW = "ufCrm7UfCrmEffRaw"
UF_EFF_FINAL = "ufCrm7UfCrmEffFinal"
UF_STATUS = "ufCrm7UfCrmStatus"
UF_PDF_FILE = "ufCrm7UfCrmPdfFile"

# Resource fields (entityTypeId = 1056)
# Общие поля
UF_SHIFT_ID = "ufCrm9UfShiftId"            # Привязка к смене
UF_RESOURCE_TYPE = "ufCrm9UfResourceType"  # "EQUIP" | "MAT"

# Техника
UF_EQUIP_TYPE = "ufCrm9UfEquipType"
UF_EQUIP_HOURS = "ufCrm9UfEquipHours"
UF_EQUIP_RATE_TYPE = "ufCrm9UfEquipRateType"
UF_EQUIP_RATE = "ufCrm9UfEquipRate"
UF_RES_COMMENT = "ufCrm9UfResComment"

# Материалы
UF_MAT_TYPE = "ufCrm9UfMatType"
UF_MAT_QTY = "ufCrm9UfMatQty"
UF_MAT_UNIT = "ufCrm9UfMatUnit"
UF_MAT_PRICE = "ufCrm9UfMatPrice"
UF_MAT_COMMENT = "ufCrm9UfMatComment"

# Timesheet fields (entityTypeId = 1060)
UF_TS_SHIFT_ID = "ufCrm11UfShiftId"
UF_TS_WORKER = "ufCrm11UfWorker"
UF_TS_HOURS = "ufCrm11UfHours"
UF_TS_RATE = "ufCrm11UfRate"
UF_TS_COMMENT = "ufCrm11UfTsComment"
