import logging
import json
import base64
from odoo import http, fields
from odoo.http import request
from werkzeug.utils import redirect
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class StajyerLocation(http.Controller):

    @http.route(['/stajyer/save_location'], type='http', auth='public', website=True, methods=['POST'])
    def save_location(self, **post):
        try:
            _logger.info("stajyer/save_location called with: %s", {k: v for k, v in post.items()})
            ref = post.get('redirect') or request.httprequest.referrer or '/stajyer/profile'
            return redirect(ref)
        except Exception:
            _logger.exception("Error in save_location")
            return redirect('/stajyer/profile')

    @http.route(['/stajyer/save_location_json'], type='json', auth='user', methods=['POST'], csrf=False)
    def save_location_json(self, **post):
        try:
            data = None
            if hasattr(request, 'jsonrequest') and request.jsonrequest:
                data = request.jsonrequest
            else:
                try:
                    data = request.httprequest.get_json(silent=True)
                except Exception:
                    data = None
                if not data:
                    try:
                        import json
                        raw = request.httprequest.get_data(as_text=True)
                        data = json.loads(raw) if raw else {}
                    except Exception:
                        data = post or {}

            _logger.info("INCOMING DATA (json): %s", data)

            # jsonrpc formatında params içinden al, yoksa direkt data'dan
            params = data.get('params', data) if isinstance(data, dict) else data
            
            lat = params.get('lat') or params.get('latitude') or params.get('location_lat')
            lng = params.get('lng') or params.get('longitude') or params.get('location_lng')
            acc = params.get('accuracy') or params.get('location_accuracy')

            if lat is None or lng is None:
                return {'success': False, 'error': 'Lat/Lng eksik'}

            user = request.env.user
            _logger.info("save_location_json called by uid=%s email=%s", getattr(user, 'id', None), getattr(user, 'email', None))

            Stajyer = request.env['stajyer.takip'].sudo()
            stajyer = None

            if user and 'user_id' in Stajyer._fields:
                stajyer = Stajyer.search([('user_id', '=', user.id)], limit=1)

            if not stajyer and getattr(user, 'email', None) and 'email' in Stajyer._fields:
                stajyer = Stajyer.search([('email', '=', user.email)], limit=1)

            if not stajyer and getattr(user, 'partner_id', False):
                if 'partner_id' in Stajyer._fields:
                    stajyer = Stajyer.search([('partner_id', '=', user.partner_id.id)], limit=1)
                elif 'partner' in Stajyer._fields:
                    stajyer = Stajyer.search([('partner', '=', user.partner_id.id)], limit=1)

            if not stajyer:
                _logger.warning("No stajyer found for uid=%s email=%s", getattr(user, 'id', None), getattr(user, 'email', None))
                return {'success': False, 'error': 'Stajyer kaydı bulunamadı (uid=%s email=%s)' % (getattr(user, 'id', None), getattr(user, 'email', None))}

            vals = {
                'location_lat': float(lat),
                'location_lng': float(lng),
                'location_date': fields.Datetime.now(),
            }
            if acc is not None:
                try:
                    vals['location_accuracy'] = float(acc)
                except Exception:
                    pass

            stajyer.sudo().write(vals)
            _logger.info("Location saved for stajyer_id=%s vals=%s", stajyer.id, vals)
            
            # Hesaplanan değerleri döndür
            return {
                'success': True,
                'distance': stajyer.distance_km,
                'fee': stajyer.fee_amount
            }

        except Exception as e:
            _logger.exception("HATA save_location_json: %s", e)
            return {'success': False, 'error': str(e)}
