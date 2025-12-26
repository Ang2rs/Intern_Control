import logging
import json
import base64
from odoo import http, fields
from odoo.http import request
from werkzeug.utils import redirect
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class StajyerMeeting(http.Controller):

    @http.route(['/stajyer/meeting/book'], type='http', auth='public', website=True, methods=['GET', 'POST'])
    def stajyer_meeting_book(self, **post):
        if request.env.user._is_public():
            return request.redirect('/web/login?redirect=/stajyer/meeting/book')

        Stajyer = request.env['stajyer.takip'].sudo()
        stajyer = Stajyer.search([('user_id', '=', request.env.user.id)], limit=1)
        if not stajyer and getattr(request.env.user, 'email', None):
             stajyer = Stajyer.search([('email', '=', request.env.user.email)], limit=1)
        
        if stajyer and stajyer.status == 'done':
            return request.redirect('/stajyer/profile')

        if request.httprequest.method == 'GET':
            return request.render('stajyer_takip.website_meeting_book', {
                'user': request.env.user,
            })

        try:
            name = (post.get('name') or '').strip()
            date = post.get('date')
            time_raw = post.get('time') or ''
            note = (post.get('note') or '').strip()

            if not name or not note:
                 return request.render('stajyer_takip.website_meeting_book', {
                    'error': 'Lütfen konu başlığı ve not alanlarını doldurunuz.',
                    'user': request.env.user,
                })
            partner = request.env.user.partner_id.id if request.env.user.partner_id else False

            time_float = 0.0
            if time_raw:
                try:
                    if ':' in time_raw:
                        h, m = map(int, time_raw.split(':'))
                        time_float = h + (m / 60.0)
                    else:
                        time_float = float(time_raw)
                except Exception:
                    _logger.warning("Invalid time value posted: %s", time_raw)

            try:
                duration = float(post.get('duration') or 0.5)
            except:
                duration = 0.5

            stajyer_id = False
            Stajyer = request.env['stajyer.takip'].sudo()
            stajyer = Stajyer.search([('user_id', '=', request.env.user.id)], limit=1)
            if not stajyer and getattr(request.env.user, 'email', None):
                 stajyer = Stajyer.search([('email', '=', request.env.user.email)], limit=1)
            if stajyer:
                stajyer_id = stajyer.id
                if stajyer.status == 'done':
                    return request.redirect('/stajyer/profile')

            # Geçmiş Zaman Kontrolü
            from datetime import datetime, timedelta
            import pytz
            
            try:
                msg_date = fields.Date.from_string(date)
                today = fields.Date.context_today(request.env.user)
                
                if msg_date < today:
                    return request.render('stajyer_takip.website_meeting_book', {
                        'error': 'Lütfen ileri bir tarihli görüşme seçiniz.',
                        'user': request.env.user,
                    })
                elif msg_date == today:
                    # Saat dilimi yönetimi - güvenli yaklaşım
                    try:
                        tz = pytz.timezone('Europe/Istanbul')
                        now = datetime.now(tz)
                    except Exception:
                        # Fallback to UTC+3 if pytz fails
                        now = datetime.utcnow() + timedelta(hours=3)
                        
                    current_time_float = now.hour + (now.minute / 60.0)
                    
                    # Sinir bozucu anlık hataları önlemek için 5 dakikalık tampon süre
                    if time_float < (current_time_float - 0.08): 
                         return request.render('stajyer_takip.website_meeting_book', {
                            'error': 'Geçilen bir saate görüşme oluşturulamaz. (Şu an: %02d:%02d)' % (now.hour, now.minute),
                            'user': request.env.user,
                        })
            except Exception as e:
                _logger.warning("Date/Time check validation error: %s", e)
                # Güvenli mod: Doğrulama kodu çökerse engelleme yapma, sadece logla.
                pass

            request.env['stajyer.meeting'].sudo().create({
                'name': name,
                'user_id': request.env.user.id,
                'stajyer_id': stajyer_id,
                'partner_id': partner,
                'date': date,
                'time': time_float,
                'time': time_float,
                'duration': duration,
                'note': note,
                'state': 'pending',
            })

            return request.redirect('/stajyer/meeting/my')

        except ValidationError as e:
            _logger.warning("Meeting validation error: %s", e.args[0])
            return request.render('stajyer_takip.website_meeting_book', {
                'error': e.args[0],
                'user': request.env.user,
            })
        except Exception as e:
            _logger.exception("Meeting create failed: %s", e)
            return request.render('stajyer_takip.website_meeting_book', {
                'error': f'Görüşme oluşturulamadı, teknik detay: {str(e)}',
                'user': request.env.user,
            })

    @http.route(['/stajyer/meeting/check_availability'], type='json', auth='public', methods=['POST'])
    def check_meeting_availability(self, **post):
        try:
            # JsonRPC params handling
            data = post
            
            date_str = data.get('date')
            time_raw = data.get('time')
            try:
                duration_val = float(data.get('duration') or 0.5)
            except:
                duration_val = 0.5
            
            if not date_str or not time_raw:
                return {'success': True} 

            time_float = 0.0
            if ':' in str(time_raw):
                h, m = map(int, str(time_raw).split(':'))
                time_float = h + (m / 60.0)
            else:
                try:
                    time_float = float(time_raw)
                except:
                    return {'success': True}

            # Küresel Çakışma Kontrolü (Sistem Geneli)
            Meeting = request.env['stajyer.meeting'].sudo()

            # Geçmiş Zaman Kontrolü (AJAX)
            from datetime import datetime, timedelta
            import pytz
            try:
                msg_date = fields.Date.from_string(date_str)
                today = fields.Date.context_today(request.env.user)
                if msg_date < today:
                     return {'success': False, 'error': "Lütfen ileri bir tarih seçiniz."}
                elif msg_date == today:
                    try:
                        tz = pytz.timezone('Europe/Istanbul')
                        now = datetime.now(tz)
                    except:
                        now = datetime.utcnow() + timedelta(hours=3)
                        
                    current_time_float = now.hour + (now.minute / 60.0)
                    
                    if time_float < (current_time_float - 0.08):
                         return {'success': False, 'error': "Geçmiş bir saate randevu oluşturulamaz. (Şu an: %02d:%02d)" % (now.hour, now.minute)}
            except Exception as e:
                _logger.error("Availability check date error: %s", e)


            domain = [
                ('date', '=', date_str),
                ('state', '!=', 'rejected'),
                ('state', '!=', 'expired')
            ]
            others = Meeting.search(domain)
            others = Meeting.search(domain)
            
            # Requested meeting
            m_start = time_float
            m_end = time_float + duration_val
            
            for other in others:
                o_start = other.time
                o_end = other.time + other.duration
                
                # Overlap logic
                if (m_start < o_end) and (o_start < m_end):
                     return {'success': False, 'error': "Bu saatte başka bir görüşme var, lütfen farklı bir saat seçiniz."}

            return {'success': True}

        except Exception as e:
            _logger.exception("Availability check failed: %s", e)
            return {'success': False, 'error': str(e)}

    @http.route(['/stajyer/meeting/my'], type='http', auth='user', website=True, methods=['GET'])
    def stajyer_meeting_my(self, **post):
        user = request.env.user.sudo()
        is_admin = bool(user.has_group('base.group_system'))

        domain = []
        if not is_admin:
            domain = [('user_id', '=', user.id)]
            stajyer = request.env['stajyer.takip'].sudo().search([('user_id', '=', user.id)], limit=1)
            if not stajyer and getattr(user, 'email', None):
                stajyer = request.env['stajyer.takip'].sudo().search([('email', '=', user.email)], limit=1)
            if stajyer and stajyer.status == 'done':
                return redirect('/stajyer/profile')

        try:
             request.env['stajyer.meeting'].sudo()._check_meeting_status()
        except Exception:
             pass

        meetings = request.env['stajyer.meeting'].sudo().search(domain)

        meetings = meetings.sorted(key=lambda m: (m.date, m.time, m.id), reverse=True)
        
        priority_map = {'pending': 0, 'accepted': 0, 'rejected': 1, 'expired': 2}
        meetings = meetings.sorted(key=lambda m: priority_map.get(m.state, 3))

        return request.render('stajyer_takip.website_meeting_my', {
            'meetings': meetings,
            'user': user,
            'is_admin_view': is_admin,
        })

    @http.route(['/stajyer/meeting/<int:meeting_id>/action'], type='http', auth='user', website=True, methods=['POST'])
    def stajyer_meeting_action(self, meeting_id, **post):
        if not request.env.user.has_group('base.group_system'):
            return redirect('/')

        action = post.get('action')
        meeting = request.env['stajyer.meeting'].sudo().browse(meeting_id)
        if meeting.exists() and action in ('accept', 'reject'):
            try:
                vals = {'state': 'accepted' if action == 'accept' else 'rejected'}
                if action == 'accept':
                    vals['host_id'] = request.env.user.id
                meeting.sudo().write(vals)
            except Exception as e:
                _logger.exception("Meeting action failed: %s", e)

        return redirect('/stajyer/meeting/my')
