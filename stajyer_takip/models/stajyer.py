from odoo import api, fields, models
from datetime import timedelta
from odoo.exceptions import ValidationError


class StajyerDepartment(models.Model):
    _name = "stajyer.department"
    _description = "Stajyer Departmanı"

    name = fields.Char("Departman Adı", required=True)


class Stajyer(models.Model):
    _name = "stajyer.takip"
    _description = "Stajyer"
    _rec_name = "name"
    _order = "start_date desc, name asc"

    name = fields.Char("Ad Soyad", required=True)
    email = fields.Char("E-posta")
    phone = fields.Char("Telefon")
    yas = fields.Integer("Yaş", required=False, default=0)
    department = fields.Many2one('stajyer.department', string="Departman")





    mentor_id = fields.Many2one("res.users", string="Mentör")
    user_id = fields.Many2one("res.users", string="Kullanıcı", help="Bu stajyer kaydını oluşturan kullanıcı.")

    start_date = fields.Date(string="Başlangıç Tarihi", default=fields.Date.context_today)
    end_date = fields.Date(
    string="Bitiş Tarihi",
    default=lambda self: (fields.Date.today() + timedelta(days=119))
    )


    active = fields.Boolean(default=True, string="Aktif")

    status = fields.Selection([ 
        ("draft", "Aday"),
        ("ongoing", "Devam Ediyor"),
        ("paused", "Askıda"),
        ("done", "Tamamlandı"),
        ("cancel", "İptal"),
    ], string="Durum", default="draft", tracking=True)

    progress = fields.Integer("İlerleme (%)", default=0)
    notes = fields.Text("Notlar")

    duration_days = fields.Integer("Toplam Gün", compute="_compute_duration", store=True)

    log_ids = fields.One2many("stajyer.log", "stajyer_id", string="Loglar")
    log_count = fields.Integer(compute="_compute_counts", string="Log Sayısı")
    
    meeting_ids = fields.One2many("stajyer.meeting", "stajyer_id", string="Görüşmeler")
    meeting_count = fields.Integer(compute="_compute_counts", string="Görüşme Sayısı")
    
    daily_work_ids = fields.One2many("stajyer.daily.work", "stajyer_id", string="Günlük Çalışmalar")
    daily_work_count = fields.Integer(compute="_compute_counts", string="Çalışma Sayısı")

    quiz_progress_ids = fields.One2many("stajyer.roadmap.progress", "stajyer_id", string="Quizler")
    quiz_count = fields.Integer(compute="_compute_counts", string="Quiz Sayısı")

    skill_ids = fields.Many2many('stajyer.skill', string='Yetenekler', help='Stajyerin bildiği teknolojiler/yetenekler')
    ortalama_puan = fields.Float(string="Ortalama Puan", compute="_compute_ortalama_puan", store=True)

    @api.constrains('yas')
    def _check_yas(self):
        for rec in self:
            if rec.yas is not None and rec.yas < 13:
                raise ValidationError("Stajyer yaşı 13'ten küçük olamaz.")

    @api.depends("start_date", "end_date")  
    def _compute_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                rec.duration_days = (fields.Date.from_string(rec.end_date) - fields.Date.from_string(rec.start_date)).days + 1
            else:
                rec.duration_days = 0

    @api.model
    def _cron_update_progress(self):
        today = fields.Date.context_today(self)
        stajyerler = self.search([('status', '=', 'ongoing')])
        for rec in stajyerler:
            if rec.start_date and rec.duration_days and rec.duration_days > 0:
                elapsed = (today - rec.start_date).days + 1
                if elapsed < 0:
                    elapsed = 0
                pct = min(100, int(elapsed * 100.0 / rec.duration_days))
                if rec.progress != pct:
                    rec.progress = pct
                if pct >= 100:
                    rec.status = 'done'
            else:
                rec.progress = 0

    @api.depends('log_ids', 'meeting_ids', 'daily_work_ids', 'quiz_progress_ids')
    def _compute_counts(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)
            rec.meeting_count = len(rec.meeting_ids)
            rec.daily_work_count = len(rec.daily_work_ids)
            rec.quiz_count = len(rec.quiz_progress_ids)

    def action_open_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Loglar',
            'res_model': 'stajyer.log',
            'view_mode': 'list,form',
            'domain': [('stajyer_id', '=', self.id)],
            'context': {'default_stajyer_id': self.id},
        }

    def action_open_meetings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Görüşmeler',
            'res_model': 'stajyer.meeting',
            'view_mode': 'list,form,calendar',
            'domain': [('stajyer_id', '=', self.id)],
            'context': {'default_stajyer_id': self.id},
        }

    def action_open_daily_works(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Günlük Çalışmalar',
            'res_model': 'stajyer.daily.work',
            'view_mode': 'list,form',
            'domain': [('stajyer_id', '=', self.id)],
        }

    def action_open_quizzes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quizler',
            'res_model': 'stajyer.roadmap.progress',
            'view_mode': 'list,form',
            'domain': [('stajyer_id', '=', self.id)],
            'context': {'default_stajyer_id': self.id},
        }

    @api.depends("log_ids", "log_ids.puan") 
    def _compute_ortalama_puan(self):
        for rec in self:
            logs = rec.log_ids.filtered(lambda l: l.puan not in (None, False))
            if logs:
                puanlar = [float(l.puan) for l in logs]
                rec.ortalama_puan = sum(puanlar) / len(puanlar)
            else:
                rec.ortalama_puan = 0.0

    completion_date = fields.Date(string="Tamamlanma Tarihi", readonly=True)

    def write(self, vals):
        if vals.get('status') == 'done':
            vals['completion_date'] = fields.Date.context_today(self)
        return super(Stajyer, self).write(vals)