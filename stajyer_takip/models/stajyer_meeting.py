from odoo import models, fields, api
import logging
from datetime import timedelta
import pytz

_logger = logging.getLogger(__name__)

from odoo.exceptions import ValidationError

class StajyerMeeting(models.Model):
    _name = 'stajyer.meeting'
    _description = 'Stajyer Görüşmesi'
    _order = 'date desc, time asc'

    name = fields.Char(string='Başlık', required=True)
    user_id = fields.Many2one('res.users', string='Kullanıcı', default=lambda self: self.env.user, required=True)
    partner_id = fields.Many2one('res.partner', string='Partner', help='Kullanıcının partner kaydı (opsiyonel)')
    date = fields.Date(string='Tarih', required=True)
    time = fields.Float(string='Saat')
    duration = fields.Float(string='Süre (Saat)', default=0.5)
    note = fields.Text(string='Not')
    stajyer_id = fields.Many2one('stajyer.takip', string='Stajyer', ondelete='cascade')
    mentor_id = fields.Many2one('res.users', related='stajyer_id.mentor_id', string='Mentör', store=True, readonly=True)
    host_id = fields.Many2one('res.users', string='Görüşme Sahibi')
    
    calendar_event_id = fields.Many2one('calendar.event', string='Takvim Etkinliği', ondelete='set null')
    
    state = fields.Selection([
        ('pending', 'Beklemede'),
        ('accepted', 'Kabul Edildi'),   
        ('rejected', 'Reddedildi'),
        ('expired', 'Süresi Doldu'),
        ('completed', 'Tamamlandı')
    ], default='pending', string='Durum')
    create_date = fields.Datetime(string='Oluşturulma Tarihi', readonly=True)

    @api.constrains('mentor_id', 'stajyer_id', 'date', 'time')
    def _check_meeting_overlap(self):
        for meeting in self:
            if not meeting.date or not meeting.time:
                continue
            

            domain = [
                ('id', '!=', meeting.id),
                ('date', '=', meeting.date),
                ('state', '!=', 'rejected'),
                ('state', '!=', 'expired') 
            ]
            others = self.search(domain)
            
            m_start = meeting.time
            m_end = meeting.time + meeting.duration

            for other in others:
                o_start = other.time
                o_end = other.time + other.duration
                
                if (m_start < o_end) and (o_start < m_end):
                     raise ValidationError(f"Bu saat aralığında ({o_start:.2f} - {o_end:.2f}) sistemde başka bir görüşme mevcut. Lütfen başka bir saat seçiniz.")


            if meeting.stajyer_id:
                domain = [
                    ('id', '!=', meeting.id),
                    ('stajyer_id', '=', meeting.stajyer_id.id),
                    ('date', '=', meeting.date),
                    ('state', '!=', 'rejected'),
                    ('state', '!=', 'expired')
                ]
                others = self.search(domain)
                for other in others:
                    o_start = other.time
                    o_end = other.time + other.duration
                    if (m_start < o_end) and (o_start < m_end):
                        raise ValidationError("Bu saat aralığında sizin başka bir görüşmeniz mevcut.")

    @api.model
    def create(self, vals):
        meeting = super(StajyerMeeting, self).create(vals)
        if meeting.date and meeting.time:
             meeting._create_or_update_calendar_event()
        return meeting

    def write(self, vals):
        res = super(StajyerMeeting, self).write(vals)
        for meeting in self:
            if 'date' in vals or 'time' in vals or 'state' in vals:
                meeting._create_or_update_calendar_event()
        return res

    def _create_or_update_calendar_event(self):
        self.ensure_one()
        if self.state != 'accepted':
             if self.calendar_event_id:
                 self.calendar_event_id.unlink()
             return


        
        
        user_tz = 'Europe/Istanbul'
        try:
            local_tz = pytz.timezone(user_tz)
        except:
             local_tz = pytz.timezone('Europe/Istanbul')


        naive_dt = fields.Datetime.to_datetime(self.date) + timedelta(hours=self.time)
        

        local_dt = local_tz.localize(naive_dt, is_dst=None)
        

        utc_dt = local_dt.astimezone(pytz.UTC)
        
        start_datetime = fields.Datetime.to_string(utc_dt)
        stop_datetime = fields.Datetime.to_string(utc_dt + timedelta(minutes=self.duration*60))
        
        partner_ids = [self.user_id.partner_id.id] 
        if self.mentor_id:
            partner_ids.append(self.mentor_id.partner_id.id) # Mentor
        if self.host_id and self.host_id.partner_id:
            partner_ids.append(self.host_id.partner_id.id) # (Admin)

        vals = {
            'name': f"Mülakat/Görüşme: {self.name}",
            'start': start_datetime,
            'stop': stop_datetime,
            'duration': self.duration,
            'user_id': self.host_id.id or self.env.user.id,
            'partner_ids': [(6, 0, partner_ids)],
            'description': f"Stajyer: {self.stajyer_id.name}\nNot: {self.note or ''}",
            'videocall_source': 'discuss', 
        }


        if self.calendar_event_id:
            self.calendar_event_id.sudo().write(vals)
        else:
            event = self.env['calendar.event'].sudo().create(vals)
            self.calendar_event_id = event.id
            
            try:
                channel = self.env['discuss.channel'].sudo().create({
                    'name': f"Mülakat: {self.name}",
                    'channel_type': 'channel',
                    'group_public_id': None,
                    'group_ids': [(6, 0, [])]
                })
                channel.add_members(partner_ids=partner_ids)
                
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                video_url = f"{base_url}/discuss/channel/{channel.id}"
                
                event.sudo().write({
                    'videocall_location': video_url,
                    'location': video_url
                })
            except Exception as e:
                _logger.error("Manual Channel creation failed: %s", e)
        
        try:
            if self.calendar_event_id.videocall_source == 'discuss' and not self.calendar_event_id.videocall_location:
                self.calendar_event_id.sudo()._create_videocall_location()
        except Exception as e:
            _logger.warning("Could not create videocall location: %s", e)

    @api.model
    def _check_meeting_status(self):

        now_utc = fields.Datetime.now()
        
        today = fields.Date.context_today(self)
        
        meetings = self.search([
            ('state', 'in', ['pending', 'accepted', 'rejected']),
            ('date', '<=', today)
        ])
        
        count_expired = 0
        count_completed = 0
        
        
        system_tz = pytz.timezone('UTC') 
      
        tz_name = 'Europe/Istanbul'
        local_tz = pytz.timezone(tz_name)

        for m in meetings:
            if not m.date or not m.time:
                continue
                
            duration_hours = m.duration if m.duration else 0.5
            naive_start = fields.Datetime.to_datetime(m.date) + timedelta(hours=m.time)
            naive_end = naive_start + timedelta(hours=duration_hours)
            
            local_end = local_tz.localize(naive_end, is_dst=None)
            
            end_utc = local_end.astimezone(pytz.UTC)
            

            end_utc_naive = end_utc.replace(tzinfo=None)
            
            if end_utc_naive < now_utc:
                if m.state == 'pending':
                    m.write({'state': 'expired'})
                    count_expired += 1
                elif m.state == 'rejected':
                    m.write({'state': 'expired'})
                    count_expired += 1
                elif m.state == 'accepted':
                    m.write({'state': 'completed'})
                    count_completed += 1

        if count_expired or count_completed:
            _logger.info(f"Cron Update: {count_expired} expired, {count_completed} completed.")