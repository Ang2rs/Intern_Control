import logging
import json
import base64
from odoo import http, fields
from odoo.http import request
from werkzeug.utils import redirect
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class StajyerProfile(http.Controller):

    @http.route(['/stajyer/signup'], type='http', auth='public', website=True, methods=['GET', 'POST'])
    def stajyer_signup(self, **post):
        if request.env.user and not request.env.user._is_public():
            return redirect('/stajyer/profile')

        if request.httprequest.method == 'GET':
            return request.render('stajyer_takip.website_stajyer_signup')

        name = (post.get('name') or '').strip()
        email = (post.get('email') or '').strip().lower()
        password = (post.get('password') or '').strip()
        yas_str = (post.get('yas') or '0').strip()

        try:
            yas = int(yas_str)
        except ValueError:
            yas = 0

        if not name or not email or not password:
            return request.render('stajyer_takip.website_stajyer_signup', {
                'error': 'Lütfen tüm alanları doldurun.',
                'name': name,
                'email': email,
                'yas': yas_str,
            })

        try:
            User = request.env['res.users'].sudo()
            Stajyer = request.env['stajyer.takip'].sudo()

            request.env.cr.flush()

            existing_user = User.with_context(active_test=False).search([('login', '=', email)], limit=1)

            if existing_user:
                if not existing_user.active:
                    existing_user.sudo().write({'active': True})
                else:
                    return request.render('stajyer_takip.website_stajyer_signup', {
                        'error': 'Bu e-posta adresiyle zaten bir hesap var. Lütfen giriş yapın.',
                    })
                user = existing_user
            else:
                portal_group = request.env.ref('base.group_portal')

                user = User.create({
                    'name': name,
                    'login': email,
                    'email': email,
                    'password': password,
                    'share': True,
                    'groups_id': [(6, 0, [portal_group.id])],
                })

            existing_stajyer = Stajyer.search([('email', '=', email)], limit=1)
            if existing_stajyer:
                _logger.info("Stajyer zaten mevcut: %s", existing_stajyer.id)
                stajyer = existing_stajyer
            else:
                stajyer_vals = {
                    'name': name,
                    'email': email,
                    'yas': yas,
                    'user_id': user.id,
                }
                stajyer = Stajyer.create(stajyer_vals)

            _logger.info("Stajyer kaydı oluşturuldu: %s", stajyer.id)

            try:
                request.session.authenticate(email, password)
            except TypeError:
                db = request.env.cr.dbname
                request.session.authenticate(db, email, password)
            except Exception as e:
                _logger.warning("Otomatik giriş başarısız: %s", e)

            return redirect('/stajyer/profile')

        except Exception as e:
            _logger.exception("Signup failed: %s", e)
            return request.render('stajyer_takip.website_stajyer_signup', {
                'error': f'Kayıt oluşturulamadı: {str(e)}',
            })

    @http.route(['/stajyer/profile'], type='http', auth='user', website=True)
    def stajyer_profile(self, **kw):
        req_id = kw.get('id')
        current_uid = request.session.uid or (request.uid if hasattr(request, 'uid') else None)
        current_user = request.env['res.users'].sudo().browse(current_uid) if current_uid else None
        is_admin = bool(current_user and current_user.has_group('base.group_system'))

        Stajyer = request.env['stajyer.takip'].sudo()
        stajyer = None

        if req_id:
            try:
                stajyer_id = int(req_id)
            except (TypeError, ValueError):
                return request.not_found()
            stajyer = Stajyer.browse(stajyer_id)
            if not stajyer.exists():
                return request.not_found()
            owner_ok = bool(stajyer.user_id and current_user and stajyer.user_id.id == current_user.id)
            if not (is_admin or owner_ok):
                return redirect('/web/login')
        else:
            stajyer = Stajyer.search([('user_id', '=', current_uid)], limit=1)
            if not stajyer:
                stajyer = Stajyer.search([], limit=1)
                if not stajyer:
                    return redirect('/')

        if stajyer and stajyer.status == 'done' and not is_admin:
            return request.render('stajyer_takip.certificate_view', {'stajyer': stajyer})

        can_edit = bool(is_admin)

        users = request.env['res.users'].sudo().search([], order='name') if is_admin else request.env['res.users'].sudo().browse([])
        stajyer_list = request.env['stajyer.takip'].sudo().search([], order='name') if is_admin else request.env['stajyer.takip'].sudo().browse([])

        logs = []
        try:
            if request.env['ir.model'].sudo().search([('model', '=', 'stajyer.log')], limit=1) and stajyer:
                logs = request.env['stajyer.log'].sudo().search([('stajyer_id', '=', stajyer.id)], order='tarih desc, create_date desc')
        except Exception as e:
            _logger.debug("stajyer_profile: log model hata: %s", e)
            logs = []

        if stajyer:
            puan_average = stajyer.ortalama_puan
        else:
            puan_average = 0.0

        today_date = fields.Date.context_today(request.env.user) if request.env else fields.Date.today()

        departman_list = []
        try:
            if stajyer and 'department' in stajyer._fields:
                field = stajyer._fields['department']
                if getattr(field, 'comodel_name', False):
                    departman_list = request.env[field.comodel_name].sudo().search([], order='name')
        except Exception as e:
            _logger.debug("departman_list load failed: %s", e)

        # Get all skills for admin/owner form
        is_owner = stajyer and stajyer.user_id and stajyer.user_id.id == current_uid
        all_skills = request.env['stajyer.skill'].sudo().search([], order='name') if (is_admin or is_owner) else []

        qcontext = {
            'stajyer': stajyer,
            'can_edit': can_edit,
            'is_admin': is_admin,
            'users': users,
            'stajyer_list': stajyer_list,
            'current_uid': current_uid,
            'logs': logs,
            'puan_average': puan_average,
            'today': today_date,
            'departman_list': departman_list,

            'all_skills': all_skills,
        }

        return request.render('stajyer_takip.website_stajyer_profile', qcontext)

    @http.route(['/stajyer/profile/log/add'], type='http', auth='user', website=True, methods=['POST'])
    def stajyer_profile_log_add(self, **post):
        user = request.env.user
        if not user.has_group('base.group_system'):
            return redirect('/web/login')
        try:
            stajyer_id = int(post.get('stajyer_id') or 0)
        except (TypeError, ValueError):
            return redirect('/stajyer/profile')
        title = (post.get('name') or post.get('title') or '').strip()
        date_val = (post.get('tarih') or post.get('date') or '').strip()
        aciklama = (post.get('aciklama') or post.get('body') or '').strip()
        puan_val = (post.get('puan') or post.get('score') or post.get('point') or '').strip()

        if not stajyer_id or not (title or aciklama):
            return redirect('/stajyer/profile?id=%s' % stajyer_id)

        try:
            log_model = request.env['stajyer.log'].sudo()
            if request.env['ir.model'].sudo().search([('model', '=', 'stajyer.log')], limit=1):
                vals = {'stajyer_id': stajyer_id, 'user_id': user.id}
                if title:
                    vals['name'] = title
                if aciklama:
                    vals['aciklama'] = aciklama
                if date_val:
                    vals['tarih'] = date_val
                if puan_val:
                    try:
                        pv = int(float(puan_val))
                        vals['puan'] = pv
                    except Exception:
                        pass
                allowed = set(log_model._fields.keys())
                safe_vals = {k: v for k, v in vals.items() if k in allowed}
                if safe_vals:
                    log_model.create(safe_vals)
        except Exception as e:
            _logger.exception("stajyer_profile_log_add: create failed: %s", e)
        return redirect('/stajyer/profile?id=%s' % stajyer_id)

    def _resolve_or_create_department(self, post):
        dept_id_post = (post.get('department') or '').strip()
        dept_name = (post.get('department_display') or '').strip()

        if dept_id_post.isdigit():
            return int(dept_id_post)

        DeptModel = request.env['stajyer.department'].sudo()
        if dept_name:
            existing = DeptModel.search([('name', '=', dept_name)], limit=1)
            if existing:
                return existing.id

            try:
                new_dept = DeptModel.create({'name': dept_name})
                _logger.info("Yeni departman oluşturuldu: %s", dept_name)
                return new_dept.id
            except Exception as e:
                _logger.exception("Departman oluşturulamadı: %s", e)
                return None

        return None

    @http.route(['/stajyer/profile/update'], type='http', auth='user', website=True, methods=['POST'])
    def stajyer_profile_update(self, **post):
        if not request.env.user.has_group('base.group_system'):
            return redirect('/stajyer/profile?id=%s' % (post.get('stajyer_id') or ''))

        try:
            stajyer_id = int(post.get('stajyer_id') or 0)
        except (TypeError, ValueError):
            return redirect('/stajyer/profile')

        stajyer = request.env['stajyer.takip'].sudo().browse(stajyer_id)
        if not stajyer.exists():
            return redirect('/stajyer/profile')

        vals = {}
        if post.get('name') is not None:
            vals['name'] = (post.get('name') or '').strip()
        if post.get('email') is not None:
            vals['email'] = (post.get('email') or '').strip()
        if post.get('phone') is not None:
            vals['phone'] = (post.get('phone') or '').strip()
        if post.get('yas'):
            try:
                vals['yas'] = int(post.get('yas'))
            except Exception:
                vals['yas'] = 0

        if post.get('status') is not None:
            vals['status'] = post.get('status')
        if post.get('start_date'):
            vals['start_date'] = post.get('start_date')
        if post.get('end_date'):
            vals['end_date'] = post.get('end_date')
            
        # Checkbox işaretli değilse post'ta gelmez
        vals['active'] = bool(post.get('active'))

        if post.get('mentor_id'):
            try:
                vals['mentor_id'] = int(post.get('mentor_id'))
            except Exception:
                pass

        try:
            dept_id = self._resolve_or_create_department(post)
            if dept_id:
                StajyerModel = request.env['stajyer.takip']
                field_name = None
                for fname in ('department', 'department_id'):
                    f = StajyerModel._fields.get(fname)
                    if f and f.type == 'many2one':
                        field_name = fname
                        break
                if not field_name and 'department' in StajyerModel._fields:
                    field_name = 'department'
                if field_name:
                    vals[field_name] = int(dept_id)
                else:
                    _logger.warning("Stajyer modelinde uygun department many2one alanı bulunamadı.")
        except Exception:
            _logger.exception("Departman çözümleme/ataama sırasında hata")

        # Skill_ids (kontrol kutuları, birden fazla değer olabilir veya tek olabilir)
        skill_ids_raw = request.httprequest.form.getlist('skill_ids')
        if skill_ids_raw:
            try:
                skill_ids = [int(sid) for sid in skill_ids_raw if sid]
                vals['skill_ids'] = [(6, 0, skill_ids)]  # Replace all
            except Exception:
                _logger.exception("skill_ids parse failed")
        else:
            # Boş olması tüm yeteneklerin silindiği anlamına gelir
            vals['skill_ids'] = [(5, 0, 0)]

        vals = {k: v for k, v in vals.items() if v is not None and v != ''}
        try:
            stajyer.sudo().write(vals)
        except Exception:
            _logger.exception("stajyer update failed")
            return redirect('/stajyer/profile?id=%s' % stajyer_id)

        return redirect('/stajyer/profile?id=%s' % stajyer.id)

    @http.route(['/stajyer/profile/self-update'], type='http', auth='user', website=True, methods=['POST'])
    def stajyer_profile_self_update(self, **post):
        """Allow profile owner to update their own basic info."""
        current_uid = request.env.user.id
        
        try:
            stajyer_id = int(post.get('stajyer_id') or 0)
        except (TypeError, ValueError):
            _logger.warning("Invalid stajyer_id in self-update")
            return redirect('/stajyer/profile')
        
        stajyer = request.env['stajyer.takip'].sudo().browse(stajyer_id)
        if not stajyer.exists():
            _logger.warning("Stajyer not found for self-update: %s", stajyer_id)
            return redirect('/stajyer/profile')
        
        # Verify ownership
        if not stajyer.user_id or stajyer.user_id.id != current_uid:
            _logger.warning("Unauthorized self-update attempt by user %s for stajyer %s", 
                          request.env.user.login, stajyer_id)
            return redirect('/stajyer/profile?id=%s' % stajyer_id)
        
        # Only allow limited fields for self-update
        vals = {}
        
        name = post.get('name', '').strip()
        if name:
            vals['name'] = name
            # Also update linked user's name
            if stajyer.user_id:
                stajyer.user_id.sudo().write({'name': name})
        
        email = post.get('email', '').strip()
        if email:
            vals['email'] = email
        
        phone = post.get('phone', '').strip()
        vals['phone'] = phone  # Allow empty
        
        yas = post.get('yas')
        if yas:
            try:
                vals['yas'] = int(yas)
            except (TypeError, ValueError):
                pass
        
        # Handle skill_ids
        skill_ids_raw = request.httprequest.form.getlist('skill_ids')
        if skill_ids_raw:
            try:
                skill_ids = [int(sid) for sid in skill_ids_raw if sid]
                vals['skill_ids'] = [(6, 0, skill_ids)]
            except Exception:
                _logger.exception("skill_ids parse failed in self-update")
        else:
            vals['skill_ids'] = [(5, 0, 0)]
        
        try:
            stajyer.sudo().write(vals)
            _logger.info("Self-update successful for stajyer %s by user %s", stajyer_id, request.env.user.login)
        except Exception:
            _logger.exception("Self-update failed for stajyer %s", stajyer_id)
        
        return redirect('/stajyer/profile?id=%s' % stajyer.id)

    @http.route(['/stajyer/profile/log/delete'], type='http', auth='user', website=True, methods=['POST'])
    def stajyer_profile_log_delete(self, **post):
        if not request.env.user.has_group('base.group_system'):
            _logger.warning("Unauthorized log delete attempt by user %s", request.env.user.login)
            stajyer_id = post.get('stajyer_id') or ''
            return redirect('/stajyer/profile?id=%s' % stajyer_id)

        try:
            log_id = int(post.get('log_id') or 0)
        except (TypeError, ValueError):
            log_id = 0
        try:
            stajyer_id = int(post.get('stajyer_id') or 0)
        except (TypeError, ValueError):
            stajyer_id = 0

        if log_id:
            try:
                log = request.env['stajyer.log'].sudo().browse(log_id)
                if log.exists():
                    log.sudo().unlink()
            except Exception as e:
                _logger.exception("stajyer_profile_log_delete: unlink failed: %s", e)
        return redirect('/stajyer/profile?id=%s' % stajyer_id)

    def _create_portal_user_for_stajyer(self, stajyer, password):
        if not stajyer or not getattr(stajyer, 'email', False):
            return (None, None)
        if not password:
            _logger.warning("Portal user creation skipped: password is required for %s", stajyer.email)
            return (None, None)
        User = request.env['res.users'].sudo()
        existing = User.search([('login', '=', stajyer.email)], limit=1)
        if existing:
            return (existing, None)
        try:
            portal_group = request.env.ref('base.group_portal')
        except Exception:
            portal_group = None
        vals = {
            'name': stajyer.name or 'Stajyer',
            'login': stajyer.email,
            'password': password,
        }
        try:
            new_user = User.sudo().create(vals)
            try:
                if portal_group:
                    new_user.sudo().write({'groups_id': [(4, portal_group.id)]})
                new_user.sudo().write({'share': True})
                if 'user_id' in stajyer._fields:
                    stajyer.sudo().write({'user_id': new_user.id})
            except Exception:
                _logger.exception("assigning portal group failed (non-fatal)")
            return (new_user, password)
        except Exception:
            _logger.exception("creating portal user failed")
            return (None, None)

    @http.route(['/stajyer/create'], type='http', auth='public', website=True, methods=['POST'])
    def stajyer_create(self, **post):
        name = (post.get('name') or '').strip()
        email = (post.get('email') or '').strip()
        password = (post.get('password') or '').strip()
        if not name or not email or not password:
            return request.render('stajyer_takip.create_failed', {'error': 'Lütfen ad, e-posta ve parola girin.'})

        vals = {
            'name': name,
            'email': email,
        }
        try:
            stajyer = request.env['stajyer.takip'].sudo().create(vals)
        except Exception as e:
            _logger.exception("stajyer create failed: %s", e)
            return request.render('stajyer_takip.create_failed', {'error': 'Kayıt oluşturulamadı, lütfen tekrar deneyin.'})

        try:
            user, pwd = self._create_portal_user_for_stajyer(stajyer, password)
            try:
                db = request.session.db or request.env.cr.dbname
                if user and pwd:
                    request.session.authenticate(db, user.login, pwd)
                elif user and password:
                    try:
                        request.session.authenticate(db, user.login, password)
                    except Exception:
                        _logger.exception("authenticate existing user failed (non-fatal)")
            except Exception:
                _logger.exception("portal auth failed (non-fatal)")
        except Exception:
            _logger.exception("portal user workflow failed (non-fatal)")

        return redirect('/stajyer/profile?id=%s' % stajyer.id)

    @http.route(['/stajyer/profile/delete'], type='http', auth='user', website=True, methods=['POST'])
    def stajyer_profile_delete(self, **post):
        user = request.env.user
        is_admin = bool(user and user.has_group('base.group_system'))
        if not is_admin:
            return redirect('/stajyer/profile?id=%s' % (post.get('stajyer_id') or ''))

        try:
            stajyer_id = int(post.get('stajyer_id') or 0)
        except (TypeError, ValueError):
            stajyer_id = 0

        if stajyer_id:
            if stajyer_id in (17, 18):
                return request.redirect('/stajyer/profile?id=%s' % stajyer_id)

            try:
                stajyer = request.env['stajyer.takip'].sudo().browse(stajyer_id)
                if stajyer.exists():
                    try:
                        user = stajyer.user_id
                        if user:
                            is_portal = user.has_group('base.group_portal')
                            is_internal = user.has_group('base.group_user')
                            if is_portal and not is_internal:
                                user.sudo().unlink()
                    except Exception:
                        _logger.exception("failed to remove/deactivate linked portal user (non-fatal)")
                    stajyer.sudo().unlink()
                    return request.redirect('/stajyer/profile')
            except Exception as e:
                _logger.exception("stajyer_profile_delete failed: %s", e)
                return request.redirect('/stajyer/profile?id=%s' % stajyer_id)

        return request.redirect('/stajyer/profile')

    @http.route(['/stajyer/certificate/verify'], type='http', auth='user', website=True, methods=['GET'])
    def stajyer_certificate_verify(self, **kw):
        stajyer_id = kw.get('id')
        stajyer = None
        
        user = request.env.user
        is_admin = user.has_group('base.group_system')

        if stajyer_id:
            try:
                stajyer = request.env['stajyer.takip'].sudo().browse(int(stajyer_id))
                if not stajyer.exists() or stajyer.status != 'done':
                    stajyer = None
                else:
                    if not is_admin and stajyer.user_id.id != user.id:
                        return request.render('website.403')
            except Exception:
                stajyer = None
    
        return request.render('stajyer_takip.certificate_verify', {'stajyer': stajyer})
