import logging
import json
import base64
from odoo import http, fields
from odoo.http import request
from werkzeug.utils import redirect
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class StajyerDaily(http.Controller):

    @http.route(['/stajyer/daily'], type='http', auth='user', website=True, methods=['GET'])
    def stajyer_daily_page(self, date=None, stajyer_id=None, **kw):
        user = request.env.user
        Stajyer = request.env['stajyer.takip'].sudo()
        is_admin = bool(user.has_group('base.group_system'))
        
        stajyer = None
        stajyer_list = []

        if is_admin:
            stajyer_list = Stajyer.search([], order='name')
            if stajyer_id:
                try:
                    stajyer = Stajyer.browse(int(stajyer_id))
                except:
                    pass
            
            if not stajyer:

                stajyer = Stajyer.search([('user_id', '=', user.id)], limit=1)
                
            if not stajyer and stajyer_list:

                    stajyer = stajyer_list[0]
        else:

            stajyer = Stajyer.search([('user_id', '=', user.id)], limit=1)
            if not stajyer and getattr(user, 'email', None):
                stajyer = Stajyer.search([('email', '=', user.email)], limit=1)
            
        if not stajyer:
             return request.render('stajyer_takip.daily_work_page', {'stajyer': None})

        if stajyer.status == 'done' and not is_admin:
            return redirect('/stajyer/profile')

        # Tarih işlemleri
        from datetime import datetime, timedelta
        
        if date:
            try:
                current_date = fields.Date.from_string(date)
            except ValueError:
                current_date = fields.Date.today()
        else:
            current_date = fields.Date.today()
            
        prev_date = current_date - timedelta(days=1)
        next_date = current_date + timedelta(days=1)
        
        # Kaydı bul veya boş
        DailyWork = request.env['stajyer.daily.work'].sudo()
        daily_work = DailyWork.search([
            ('stajyer_id', '=', stajyer.id),
            ('date', '=', current_date)
        ], limit=1)
        
        return request.render('stajyer_takip.daily_work_page', {
            'stajyer': stajyer,
            'daily_work': daily_work,
            'current_date': current_date,
            'prev_date': prev_date,
            'next_date': next_date,
            'is_admin': is_admin,
            'stajyer_list': stajyer_list,
            'today': fields.Date.today(),
        })

    @http.route(['/stajyer/daily/save'], type='http', auth='user', website=True, methods=['POST'])
    def stajyer_daily_save(self, **post):
        user = request.env.user
        is_admin = bool(user.has_group('base.group_system'))
        
        # Adminler açıklama metnini değiştiremez
        if is_admin:
             # Sadece yönlendir, kaydetme
             return redirect('/stajyer/daily?date=%s&stajyer_id=%s' % (post.get('date'), post.get('stajyer_id')))

        Stajyer = request.env['stajyer.takip'].sudo()
        stajyer = Stajyer.search([('user_id', '=', user.id)], limit=1)
        if not stajyer and getattr(user, 'email', None):
            stajyer = Stajyer.search([('email', '=', user.email)], limit=1)
            
        if not stajyer:
            return redirect('/stajyer/daily')

        if stajyer.status == 'done':
            return redirect('/stajyer/profile')
            
        date_str = post.get('date')
        description = post.get('description')
        
        if not date_str:
            return redirect('/stajyer/daily')
            
        # Sadece bugünün tarihi için kayıt yapılabilir
        today_str = fields.Date.to_string(fields.Date.today())
        if date_str != today_str:
             return redirect('/stajyer/daily?date=%s&error=date_mismatch' % date_str)
            
        DailyWork = request.env['stajyer.daily.work'].sudo()
        daily_work = DailyWork.search([
            ('stajyer_id', '=', stajyer.id),
            ('date', '=', date_str)
        ], limit=1)
        
        try:
            img_file = post.get('image')
            img_data = None
            if hasattr(img_file, 'read'):
                file_content = img_file.read()
                if file_content:
                    img_data = base64.b64encode(file_content)

            vals = {'description': description}
            if img_data:
                vals['image'] = img_data

            if daily_work:
                daily_work.write(vals)
            else:
                vals.update({
                    'stajyer_id': stajyer.id,
                    'date': date_str,
                    'state': 'draft',
                })
                DailyWork.create(vals)
        except Exception as e:
            _logger.exception("Daily work save failed: %s", e)
            
        return redirect('/stajyer/daily?date=%s&saved=1&stajyer_id=%s' % (date_str, stajyer.id))

    @http.route(['/stajyer/daily/action'], type='http', auth='user', website=True, methods=['POST'])
    def stajyer_daily_action(self, **post):
        if not request.env.user.has_group('base.group_system'):
            return redirect('/')
            
        daily_work_id = post.get('daily_work_id')
        action = post.get('action')
        date = post.get('date')
        stajyer_id = post.get('stajyer_id')
        
        if daily_work_id and action in ('approve', 'reject'):
            dw = request.env['stajyer.daily.work'].sudo().browse(int(daily_work_id))
            if dw.exists():
                dw.write({'state': 'approved' if action == 'approve' else 'rejected'})
                
        return redirect('/stajyer/daily?date=%s&stajyer_id=%s' % (date, stajyer_id))

    @http.route(['/stajyer/daily/action/json'], type='json', auth='user', methods=['POST'])
    def stajyer_daily_action_json(self, daily_work_id, action):
        if not request.env.user.has_group('base.group_system'):
            return {'success': False, 'error': 'Yetkisiz işlem'}

        if not daily_work_id or action not in ('approve', 'reject'):
            return {'success': False, 'error': 'Geçersiz parametreler'}

        try:
            dw = request.env['stajyer.daily.work'].sudo().browse(int(daily_work_id))
            if not dw.exists():
                return {'success': False, 'error': 'Kayıt bulunamadı'}
            new_state = 'approved' if action == 'approve' else 'rejected'
            dw.write({'state': new_state})
            return {'success': True, 'state': new_state}
        except Exception as e:
            _logger.exception("Daily work action json failed: %s", e)
            return {'success': False, 'error': str(e)}
