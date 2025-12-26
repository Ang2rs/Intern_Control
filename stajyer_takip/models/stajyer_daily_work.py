from odoo import models, fields, api

class StajyerDailyWork(models.Model):
    _name = "stajyer.daily.work"
    _description = "Stajyer Günlük Çalışma Kaydı"
    _order = "date desc, id desc"

    date = fields.Date(string="Tarih", required=True, default=fields.Date.context_today)
    description = fields.Text(string="Yapılan Çalışmalar")
    image = fields.Binary(string="Görsel", attachment=True)
    
    stajyer_id = fields.Many2one('stajyer.takip', string="Stajyer", required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', string="Kullanıcı", related='stajyer_id.user_id', store=True, readonly=True)

    state = fields.Selection([
        ('draft', 'Bekliyor'),
        ('approved', 'Onaylandı'),
        ('rejected', 'Reddedildi')
    ], string="Durum", default='draft', required=True)

    _sql_constraints = [
        ('unique_stajyer_date', 'unique(stajyer_id, date)', 'Bir stajyerin bir gün için sadece bir çalışma kaydı olabilir!')
    ]
