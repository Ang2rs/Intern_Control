{
    "name": "Stajyer Takip",
    "summary": "Stajyer bilgileri, mentör, dönem yönetimi ve ilerleme takibi",
    "version": "18.0.1.0.0",
    "category": "Human Resources",
    "author": "Waresky",
    "website": "https://waresky.com",
    "license": "LGPL-3",
    "application": True,
    "installable": True,

    "depends": [
        "base",
        "website",
        "portal",
        "auth_signup",
        "calendar",
    ],

    "data": [
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "security/daily_work_security.xml",
        
        "views/stajyer_views.xml",
        "views/stajyer_log_views.xml",
        "views/backend_views.xml",
        "views/quiz_backend_views.xml",
        "views/menu_action.xml",
        "views/login_inherit.xml",
        "views/website_stajyer_templates.xml",
        "views/website_stajyer_admin_list.xml",
        "views/templates.xml",
        "views/meeting_templates.xml",
        "views/daily_work_templates.xml",
        "views/roadmap_templates.xml",
        "views/portal_inherit.xml",
        "views/report_certificate.xml",
        "views/quiz_view.xml",
        
        "data/ir.cron.xml",
        "views/stajyer_snippet.xml",
        "views/stajyer_snippet_templates.xml",
    ],

    "assets": {
        "web.assets_frontend": [
            "stajyer_takip/static/src/css/main.css",
        ],
    },

    "images": ["static/description/icon.png"],
}
