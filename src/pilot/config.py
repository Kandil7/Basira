"""
Pilot Configuration — Branch 1 settings.

This file contains pilot-specific configuration for the first branch deployment.
"""

# Pilot Settings
PILOT_CONFIG = {
    # Branch Information
    "branch_id": "branch_001",
    "branch_name": "الفرع الرئيسي",  # Main Branch
    "branch_city": "الرياض",  # Riyadh

    # Pilot Duration
    "start_date": "2025-02-01",
    "end_date": "2025-02-28",
    "duration_weeks": 4,

    # Users
    "max_users": 10,
    "pilot_users": [
        {"name": "مدير العمليات", "role": "manager", "email": "ops@company.com"},
        {"name": "مدير خدمة العملاء", "role": "manager", "email": "cx@company.com"},
        {"name": "محاسب الفرع", "role": "analyst", "email": "accountant@company.com"},
        {"name": "موظف تشغيل", "role": "operator", "email": "staff@company.com"},
    ],

    # Features Enabled
    "features": {
        "analytics": True,
        "customer_service": True,
        "pricing": True,
        "supply_chain": True,
        "document_upload": True,
    },

    # Limits
    "daily_chat_limit": 100,
    "monthly_documents": 50,

    # Monitoring
    "enable_metrics": True,
    "enable_audit_log": True,
    "alert_email": "admin@company.com",
}

# Success Metrics
SUCCESS_METRICS = {
    "response_time_target": 5.0,  # seconds
    "accuracy_target": 0.80,  # 80%
    "user_satisfaction_target": 4.0,  # out of 5
    "uptime_target": 0.99,  # 99%
    "adoption_target": 0.80,  # 80% of pilot users
}

# Training Queries by Agent
TRAINING_QUERIES = {
    "analytics": [
        "ما هي مبيعات اليوم؟",
        "ما هي الفروع الأعلى أداءً؟",
        "كم مخزون المنتجات؟",
        "قارن مبيعات هذا الشهر بالشهر الماضي",
    ],
    "customer_service": [
        "أين طلبي رقم 12345؟",
        "ما هي سياسة الإرجاع؟",
        "كيف أتصل بالفروع؟",
        "ما مواعيد العمل؟",
    ],
    "pricing": [
        "ما هي أسعار المنتجات؟",
        "هل هناك خصومات حالياً؟",
        "ما هو هامش الربح للمنتج X؟",
    ],
    "supply_chain": [
        "كم مخزون المورد X؟",
        "هل هناك طلبات شراء معلقة؟",
        "ما هي المنتجات التي تحتاج إعادة طلب؟",
    ],
}
