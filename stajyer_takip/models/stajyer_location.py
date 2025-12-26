from odoo import models, fields, api
from math import radians, sin, cos, sqrt, atan2

class StajyerLocation(models.Model):
    _inherit = 'stajyer.takip'

    location_lat = fields.Float(string='Konum Lat')
    location_lng = fields.Float(string='Konum Lng')
    location_accuracy = fields.Float(string='Konum Doğruluk (m)')
    location_date = fields.Datetime(string='Konum Zamanı')
    
    distance_km = fields.Float(string='Mesafe (km)', compute='_compute_distance_fee', store=True)
    fee_amount = fields.Float(string='Yol Ücreti (TL)', compute='_compute_distance_fee', store=True)

    @api.depends('location_lat', 'location_lng')
    def _compute_distance_fee(self):
        target_lat = 40.844444
        target_lng = 29.298169
        fee_per_km = 100.0
        
        for record in self:
            if not record.location_lat or not record.location_lng:
                record.distance_km = 0.0
                record.fee_amount = 0.0
                continue
                
            
            R = 6371 
            dlat = radians(record.location_lat - target_lat)
            dlng = radians(record.location_lng - target_lng)
            a = sin(dlat / 2)**2 + cos(radians(target_lat)) * cos(radians(record.location_lat)) * sin(dlng / 2)**2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            distance = R * c
            
            record.distance_km = distance
            record.fee_amount = distance * fee_per_km
