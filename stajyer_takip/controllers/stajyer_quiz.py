import logging
import json
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)

class StajyerQuiz(http.Controller):

    @http.route(['/stajyer/quiz'], type='http', auth='user', website=True)
    def quiz_page(self, item_id=None, **kw):
        """Quiz sayfasını render eder."""
        if not item_id:
            user = request.env.user
            stajyer = request.env['stajyer.takip'].sudo().search([('user_id', '=', user.id)], limit=1)
            if not stajyer and getattr(user, 'email', None):
                 stajyer = request.env['stajyer.takip'].sudo().search([('email', '=', user.email)], limit=1)
            
            skills_data = []
            if stajyer:
                progress_recs = request.env['stajyer.roadmap.progress'].sudo().search([
                    ('stajyer_id', '=', stajyer.id)
                ])
                progress_map = {p.roadmap_item_id.id: p.state for p in progress_recs}
                
                for skill in stajyer.skill_ids:
                    quizzes = []
                    for item in skill.roadmap_ids:
                        if item.question_ids:
                           quizzes.append({
                               'item': item,
                               'status': progress_map.get(item.id, 'todo')
                           })
                    
                    if quizzes:
                        skills_data.append({
                            'skill': skill,
                            'quizzes': quizzes
                        })

            return request.render('stajyer_takip.quiz_list_template', {
                'skills_data': skills_data
            })

            
        try:
            item = request.env['stajyer.roadmap.item'].sudo().browse(int(item_id))
            if not item.exists():
                return request.render('website.404')
                
          
            
            return request.render('stajyer_takip.quiz_page_template', {
                'item': item,
                'stajyer': request.env.user,
            })
        except Exception as e:
            _logger.exception("Quiz page error: %s", e)
            return request.make_response("Hata oluştu: " + str(e))


    @http.route(['/stajyer/quiz/get_questions'], type='json', auth='user', website=True)
    def get_questions(self, item_id):
        """İlgili roadmap maddesi için soruları getirir."""
        try:
            item = request.env['stajyer.roadmap.item'].sudo().browse(int(item_id))
            if not item.exists():
                return {'error': 'Konu bulunamadı.'}

            questions = []
            for q in item.question_ids:
                questions.append({
                    'id': q.id,
                    'text': q.question_text or '',
                    'has_image': bool(q.image),
                    'options': [
                        {'key': 'option1', 'value': q.option1},
                        {'key': 'option2', 'value': q.option2},
                        {'key': 'option3', 'value': q.option3},
                        {'key': 'option4', 'value': q.option4},
                    ]
                })

            if not questions:
                return {'error': 'Bu konu için henüz soru eklenmemiş.'}

            return {'questions': questions, 'item_name': item.name}
            
        except Exception as e:
            _logger.exception("Quiz fetch error: %s", e)
            return {'error': 'Bir hata oluştu.'}

    @http.route(['/stajyer/quiz/submit'], type='json', auth='user', website=True)
    def submit_quiz(self, item_id, answers):
        """Cevapları kontrol eder."""
        try:
            item = request.env['stajyer.roadmap.item'].sudo().browse(int(item_id))
            if not item.exists():
                return {'error': 'Konu bulunamadı.'}
            
            correct_count = 0
            total_questions = len(item.question_ids)
            answer_data = []
            
            for q_id, answer_key in answers.items():
                question = request.env['stajyer.quiz.question'].sudo().browse(int(q_id))
                if question.exists():
                    is_correct = (question.correct_answer == answer_key)
                    if is_correct:
                        correct_count += 1
                    
                    answer_data.append({
                        'question_id': question.id,
                        'selected_option': answer_key,
                        'is_correct': is_correct
                    })
            
            if total_questions == 0:
                 return {'success': False, 'message': 'Soru yok, yöneticiye bildirin.'}
                 
            score = (correct_count / total_questions) * 100
            
            passed = score >= 60
            
            user = request.env.user
            stajyer = request.env['stajyer.takip'].sudo().search([('user_id', '=', user.id)], limit=1)
            if not stajyer and getattr(user, 'email', None):
                 stajyer = request.env['stajyer.takip'].sudo().search([('email', '=', user.email)], limit=1)
            
            if stajyer:
                Progress = request.env['stajyer.roadmap.progress'].sudo()
                existing = Progress.search([
                    ('stajyer_id', '=', stajyer.id),
                    ('roadmap_item_id', '=', item.id)
                ], limit=1)
                
                new_state = 'done' if passed else 'failed'
                
                if existing:
                    existing.answer_ids.unlink()
                    
                    existing.write({
                        'state': new_state,
                        'score': score,
                        'answer_ids': [(0, 0, d) for d in answer_data]
                    })
                else:
                    Progress.create({
                        'stajyer_id': stajyer.id,
                        'roadmap_item_id': item.id,
                        'state': new_state,
                        'score': score,
                        'answer_ids': [(0, 0, d) for d in answer_data]
                    })
            
            return {
                'success': True,
                'passed': passed,
                'score': score,
                'correct_count': correct_count,
                'total_questions': total_questions,
                'message': 'Tebrikler! Konuyu başarıyla tamamladınız.' if passed else 'Maalesef barajı geçemediniz (%60). Tekrar deneyin.'
            }

        except Exception as e:
            _logger.exception("Quiz submit error: %s", e)
            return {'error': 'Bir hata oluştu.'}

    @http.route(['/stajyer/quiz/review'], type='http', auth='user', website=True)
    def quiz_review(self, item_id=None, **kw):
        """Quiz sonuçlarını ve cevapları gösterir."""
        if not item_id:
             return request.redirect('/stajyer/roadmap')
             
        try:
            item = request.env['stajyer.roadmap.item'].sudo().browse(int(item_id))
            if not item.exists():
                return request.render('website.404')
                
            user = request.env.user
            stajyer = request.env['stajyer.takip'].sudo().search([('user_id', '=', user.id)], limit=1)
            if not stajyer and getattr(user, 'email', None):
                 stajyer = request.env['stajyer.takip'].sudo().search([('email', '=', user.email)], limit=1)
            
            progress = None
            user_answers = {}
            if stajyer:
                progress = request.env['stajyer.roadmap.progress'].sudo().search([
                    ('stajyer_id', '=', stajyer.id),
                    ('roadmap_item_id', '=', item.id)
                ], limit=1)
                
                if progress:
                    for ans in progress.answer_ids:
                        user_answers[ans.question_id.id] = {
                            'selected': ans.selected_option,
                            'is_correct': ans.is_correct
                        }
            
            if not progress:
                 return request.redirect('/stajyer/roadmap')
                 
            return request.render('stajyer_takip.quiz_review_template', {
                'item': item,
                'stajyer': stajyer,
                'progress': progress,
                'user_answers': user_answers
            })
            
        except Exception as e:
            _logger.exception("Quiz review error: %s", e)
            return request.make_response("Hata oluştu: " + str(e))
