# 🔒 SaaS Plan Enforcer

Módulo para controlar límites y acceso en instancias cliente según su plan de suscripción.

## 📋 Funcionalidad

### **Controles Implementados:**
- ✅ **Límite de usuarios** - Bloquea crear más usuarios del permitido
- ✅ **Bloqueo de módulos** - Impide instalar módulos no incluidos en el plan
- ✅ **Límite de emails** - Controla emails externos por día

## 🔧 Instalación

### **En Instancias Cliente:**
1. Copiar módulo a addons path
2. Actualizar lista de apps
3. Instalar módulo
4. Verificar configuración

## ⚙️ Configuración

### **URL del Servidor Principal:**
```
Settings → Technical → Parameters → System Parameters
Key: saas.master.url
Value: https://bfb77f22cc70.ngrok-free.app
```

**Nota:** Cambiar en producción a URL real del servidor principal.

## 🎯 Cómo Funciona

1. **Cliente intenta acción** (crear usuario, instalar módulo, enviar email)
2. **Módulo consulta** al servidor principal: `POST /api/subscription/limits`
3. **Envía:** `db_name` (ej: "sub-00123")
4. **Recibe:** Límites del plan
5. **Valida:** Si excede límite → bloquea con mensaje claro

## 📊 Ejemplo de Respuesta API

```json
{
  "success": true,
  "subscription_code": "SUB-00123",
  "plan_name": "Professional Plan",
  "limits": {
    "max_users": 10,
    "max_external_emails_per_day": 100,
    "blocked_modules": ["stock*", "mrp*", "hr_payroll"]
  }
}
```

## 🔍 Debugging

### **Ver Límites Actuales:**
```
Menu: Plan Info → My Plan Limits
Click: 🔄 Refresh Limits
```

### **Verificar Caché:**
```
Settings → Technical → Parameters → System Parameters
Key: saas.plan.manager.cache
```

## ⚠️ Notas Importantes

- Cache de 1 hora para reducir llamadas API
- Límites de emergencia si servidor no responde (muy restrictivos)
- Wildcards soportados: `stock*` bloquea `stock`, `stock_account`, etc.
- Emails internos NO cuentan en el límite
