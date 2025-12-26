from odoo import api, models, fields
from odoo.exceptions import ValidationError

class StajyerLog(models.Model):
    _name = "stajyer.log"
    _description = "Stajyer Günlük Logları"

    name = fields.Char(string="Konu", required=True)
    aciklama = fields.Text(string="Açıklama")
    tarih = fields.Date(string="Tarih", default=fields.Date.context_today)
    puan = fields.Integer(string="Puan")
    stajyer_id = fields.Many2one('stajyer.takip', string="Stajyer", ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', string="Oluşturan", default=lambda self: self.env.uid)

    @api.constrains('puan')
    def _check_puan(self):
        for rec in self:
            if rec.puan is not None and (rec.puan < 0 or rec.puan > 100):
                raise ValidationError("Stajyer puanı 0 ile 100 arasında olmalıdır")
            
