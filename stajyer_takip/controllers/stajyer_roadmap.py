import logging
import json
import base64
from odoo import http, fields
from odoo.http import request
from werkzeug.utils import redirect
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class StajyerRoadmap(http.Controller):

    @http.route(['/stajyer/roadmap'], type='http', auth='user', website=True, methods=['GET'])
    def stajyer_roadmap(self, **kw):
        user = request.env.user
        is_admin = user.has_group('base.group_system')
        
        # Stajyer kaydını bul
        stajyer = request.env['stajyer.takip'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not stajyer and getattr(user, 'email', None):
             stajyer = request.env['stajyer.takip'].sudo().search([('email', '=', user.email)], limit=1)

        if stajyer and stajyer.status == 'done' and not is_admin:
            return redirect('/stajyer/profile')
        
        # Admin ise ve stajyer yoksa (veya admin modundaysa), TÜM yetenekleri göster
        skills_with_roadmap = []
        progress_map = {}

        if is_admin:
            # Admin için: Roadmap'i olan TÜM yetenekleri getir
            skills = request.env['stajyer.skill'].sudo().search([])
            for skill in skills:
                if skill.roadmap_ids:
                    skills_with_roadmap.append(skill)
        else:
            # Normal kullanıcı: Sadece kendi yetenekleri
            if stajyer and stajyer.skill_ids:
                for skill in stajyer.skill_ids:
                    if skill.roadmap_ids:
                        skills_with_roadmap.append(skill)
        
        # İlerleme Bilgilerini Al (Progress Load)
        completed_checklist_ids = []
        if stajyer:
             progress_recs = request.env['stajyer.roadmap.progress'].sudo().search([
                 ('stajyer_id', '=', stajyer.id)
             ])
             # Map: item_id -> state ('done', 'failed')
             for p in progress_recs:
                 progress_map[p.roadmap_item_id.id] = {
                     'state': p.state,
                     'score': p.score
                 }
                 completed_checklist_ids.extend(p.completed_checklist_ids.ids)
        
        return request.render('stajyer_takip.roadmap_page', {
            'stajyer': stajyer,
            'skills_with_roadmap': skills_with_roadmap,
            'is_admin': is_admin,
            'progress_map': progress_map,
            'completed_checklist_ids': completed_checklist_ids,
        })

    @http.route(['/stajyer/roadmap/add'], type='http', auth='user', website=True, methods=['POST'])
    def stajyer_roadmap_add(self, **post):
        if not request.env.user.has_group('base.group_system'):
            return redirect('/stajyer/roadmap')

        try:
            skill_id = int(post.get('skill_id') or 0)
            day = int(post.get('day') or 1)
            name = (post.get('name') or '').strip()
            description = (post.get('description') or '').strip()
            url = (post.get('url') or '').strip()

            if skill_id and name:
                 request.env['stajyer.roadmap.item'].sudo().create({
                    'skill_id': skill_id,
                    'day': day,
                    'name': name,
                    'description': description,
                    'url': url,
                })
        except Exception as e:
            _logger.exception("Roadmap item add failed: %s", e)

        return redirect('/stajyer/roadmap')

    @http.route(['/stajyer/roadmap/edit'], type='http', auth='user', website=True, methods=['POST'])
    def stajyer_roadmap_edit(self, **post):
        if not request.env.user.has_group('base.group_system'):
            return redirect('/stajyer/roadmap')
        
        try:
            item_id = int(post.get('item_id') or 0)
            day = int(post.get('day') or 1)
            name = (post.get('name') or '').strip()
            description = (post.get('description') or '').strip()
            url = (post.get('url') or '').strip()
            
            item = request.env['stajyer.roadmap.item'].sudo().browse(item_id)
            if item.exists():
                item.write({
                    'day': day,
                    'name': name,
                    'description': description,
                    'url': url
                })
        except Exception as e:
            _logger.exception("Roadmap edit failed: %s", e)
            
        return redirect('/stajyer/roadmap')

    @http.route(['/stajyer/roadmap/delete'], type='http', auth='user', website=True, methods=['POST'])
    def stajyer_roadmap_delete(self, **post):
        if not request.env.user.has_group('base.group_system'):
            return redirect('/stajyer/roadmap')
            
        try:
            item_id = int(post.get('item_id') or 0)
            item = request.env['stajyer.roadmap.item'].sudo().browse(item_id)
            if item.exists():
                item.unlink()
        except Exception as e:
            _logger.exception("Roadmap delete failed: %s", e)
            
        return redirect('/stajyer/roadmap')

    @http.route(['/stajyer/roadmap/progress'], type='http', auth='user', website=True, methods=['POST'])
    def stajyer_roadmap_progress(self, **post):
        try:
            item_id = int(post.get('item_id') or 0)
        except (ValueError, TypeError):
            item_id = 0
            
        state = post.get('state')

        user = request.env.user
        
        # Stajyer bul
        stajyer = request.env['stajyer.takip'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not stajyer and getattr(user, 'email', None):
             stajyer = request.env['stajyer.takip'].sudo().search([('email', '=', user.email)], limit=1)
             
        if not stajyer:
            return request.make_response(json.dumps({'error': 'Stajyer bulunamadı'}), headers=[('Content-Type', 'application/json')])
            
        Progress = request.env['stajyer.roadmap.progress'].sudo()
        existing = Progress.search([
            ('stajyer_id', '=', stajyer.id),
            ('roadmap_item_id', '=', int(item_id))
        ], limit=1)
        
        if state == 'reset':
            if existing:
                existing.unlink()
            return request.make_response(json.dumps({'success': True, 'state': False}), headers=[('Content-Type', 'application/json')])
        elif state in ('done', 'failed'):
            if existing:
                existing.write({'state': state})
            else:
                Progress.create({
                    'stajyer_id': stajyer.id,
                    'roadmap_item_id': int(item_id),
                    'state': state
                })
            return request.make_response(json.dumps({'success': True, 'state': state}), headers=[('Content-Type', 'application/json')])
            
        return request.make_response(json.dumps({'error': 'Invalid state'}), headers=[('Content-Type', 'application/json')])

    @http.route(['/stajyer/roadmap/toggle_checklist'], type='json', auth='user', website=True)
    def toggle_checklist(self, item_id, checklist_id, checked):
        """Checklist maddesini işaretler/kaldırır."""
        try:
            item_id = int(item_id)
            checklist_id = int(checklist_id)
        except ValueError:
            return {'error': 'Invalid IDs'}
            
        user = request.env.user
        stajyer = request.env['stajyer.takip'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not stajyer and getattr(user, 'email', None):
             stajyer = request.env['stajyer.takip'].sudo().search([('email', '=', user.email)], limit=1)
             
        if not stajyer:
            return {'error': 'Stajyer bulunamadı'}
            
        Progress = request.env['stajyer.roadmap.progress'].sudo()
        progress_rec = Progress.search([
            ('stajyer_id', '=', stajyer.id),
            ('roadmap_item_id', '=', item_id)
        ], limit=1)
        
        if not progress_rec:
            progress_rec = Progress.create({
                'stajyer_id': stajyer.id,
                'roadmap_item_id': item_id,
                'state': 'failed' # Henüz bitmedi, varsayılan
            })
            
        # Update checklist
        if checked:
            progress_rec.write({'completed_checklist_ids': [(4, checklist_id)]})
        else:
            progress_rec.write({'completed_checklist_ids': [(3, checklist_id)]})
            
        # Check completion
        item = request.env['stajyer.roadmap.item'].sudo().browse(item_id)
        all_checklist_ids = item.checklist_ids.ids
        completed_ids = progress_rec.completed_checklist_ids.ids
        
        is_all_checked = set(all_checklist_ids).issubset(set(completed_ids))
        
        qt_exists = bool(item.question_ids)
        
        if is_all_checked:
            if not qt_exists:
                # Soru yoksa ve hepsi bittiyse -> Done
                progress_rec.write({'state': 'done'})
                return {'success': True, 'all_checked': True, 'state': 'done', 'quiz_ready': False}
            else:
                 # Soru varsa -> Quiz Ready but NOT done yet
                 return {'success': True, 'all_checked': True, 'state': progress_rec.state, 'quiz_ready': True}
        else:
             # Eksik var -> Done ise geri al? (Opsiyonel, şimdilik ellemiyorum veya failed yapıyorum)
             # progress_rec.write({'state': 'failed'}) # İsteğe bağlı
             return {'success': True, 'all_checked': False, 'state': progress_rec.state}
