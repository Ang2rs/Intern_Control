from odoo import fields, models


class StajyerSkill(models.Model):
    _name = 'stajyer.skill'
    _description = 'Stajyer Yeteneği'
    _order = 'name'

    name = fields.Char(string='Yetenek', required=True)
    color = fields.Integer(string='Renk', default=0)

    roadmap_ids = fields.One2many('stajyer.roadmap.item', 'skill_id', string='Yol Haritası')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Bu yetenek zaten mevcut!')
    ]


class StajyerRoadmapItem(models.Model):
    _name = 'stajyer.roadmap.item'
    _description = 'Yetenek Yol Haritası Öğesi'
    _order = 'day, sequence, id'

    skill_id = fields.Many2one('stajyer.skill', string='Yetenek', required=True, ondelete='cascade')
    name = fields.Char(string='Konu Başlığı', required=True)
    day = fields.Integer(string='Gün', default=1, required=True, group_operator=False)
    description = fields.Text(string='Açıklama / İçerik')
    url = fields.Char(string='Kaynak Linki')
    quiz_duration = fields.Integer(string='Quiz Süresi (Dakika)', default=0, help="0 girilirse süre sınırı yoktur.")
    sequence = fields.Integer(string='Sıra', default=10)
    question_ids = fields.One2many('stajyer.quiz.question', 'roadmap_item_id', string='Sorular')
    checklist_ids = fields.One2many('stajyer.roadmap.checklist', 'roadmap_item_id', string='Kontrol Listesi')
    image = fields.Binary(string="Görsel", attachment=True)


class StajyerRoadmapChecklist(models.Model):
    _name = 'stajyer.roadmap.checklist'
    _description = 'Yol Haritası Kontrol Listesi'
    _order = 'sequence'

    roadmap_item_id = fields.Many2one('stajyer.roadmap.item', string='İlgili Konu', required=True, ondelete='cascade')
    name = fields.Char(string='Yapılacak İş', required=True)
    sequence = fields.Integer(string='Sıra', default=10)


class StajyerRoadmapProgress(models.Model):
    _name = 'stajyer.roadmap.progress'
    _description = 'Yol Haritası İlerlemesi'

    stajyer_id = fields.Many2one('stajyer.takip', string='Stajyer', required=True, ondelete='cascade')
    roadmap_item_id = fields.Many2one('stajyer.roadmap.item', string='Yol Haritası Maddesi', required=True, ondelete='cascade')
    state = fields.Selection([('done', 'Tamamlandı'), ('failed', 'Yapılamadı')], string='Durum', required=True)
    date_done = fields.Date(string='Tarih', default=fields.Date.context_today)
    completed_checklist_ids = fields.Many2many('stajyer.roadmap.checklist', string='Tamamlanan Maddeler')
    score = fields.Float(string="Puan", default=0.0)
    answer_ids = fields.One2many('stajyer.roadmap.progress.answer', 'progress_id', string='Verilen Cevaplar')

    _sql_constraints = [
        ('stajyer_item_uniq', 'unique (stajyer_id, roadmap_item_id)', 'Bu madde için kayıt zaten var!')
    ]


class StajyerRoadmapProgressAnswer(models.Model):
    _name = 'stajyer.roadmap.progress.answer'
    _description = 'Quiz Cevabı'

    progress_id = fields.Many2one('stajyer.roadmap.progress', string='İlerleme Kaydı', required=True, ondelete='cascade')
    question_id = fields.Many2one('stajyer.quiz.question', string='Soru', required=True, ondelete='cascade')
    selected_option = fields.Selection([
        ('option1', 'A'),
        ('option2', 'B'),
        ('option3', 'C'),
        ('option4', 'D')
    ], string='Seçilen Şık', required=True)
    is_correct = fields.Boolean(string='Doğru mu?', default=False)


class StajyerQuizQuestion(models.Model):
    _name = 'stajyer.quiz.question'
    _description = 'Quiz Sorusu'
    _order = 'sequence'
    _rec_name = 'question_text'

    roadmap_item_id = fields.Many2one('stajyer.roadmap.item', string='İlgili Konu', required=True, ondelete='cascade')
    question_text = fields.Text(string='Soru', required=True)
    image = fields.Binary(string="Soru Görseli", attachment=False)
    option1 = fields.Char(string='Seçenek A', required=True)
    option2 = fields.Char(string='Seçenek B', required=True)
    option3 = fields.Char(string='Seçenek C', required=True)
    option4 = fields.Char(string='Seçenek D', required=True)
    correct_answer = fields.Selection([
        ('option1', 'A'),
        ('option2', 'B'),
        ('option3', 'C'),
        ('option4', 'D')
    ], string='Doğru Cevap', required=True)
    sequence = fields.Integer(string='Sıra', default=10)
