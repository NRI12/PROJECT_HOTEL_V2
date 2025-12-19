from datetime import datetime
from flask import request, session, send_file, Response
from sqlalchemy import func
from marshmallow import ValidationError
import os
import csv
import tempfile
from app import db
from app.models.user import User
from app.models.hotel import Hotel
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.review import Review
from app.models.role import Role
from app.models.room import Room
from app.schemas.user_schema import AdminUserCreateSchema
from app.utils.response import success_response, error_response, validation_error_response, paginated_response
from app.utils.validators import normalize_email


class AdminController:
    
    @staticmethod
    def _require_admin():
        if 'user_id' not in session:
            return None, error_response('Chưa đăng nhập', 401)
        
        user = User.query.get(session['user_id'])
        if not user or user.role.role_name != 'admin':
            return None, error_response('Không có quyền truy cập', 403)
        return user, None
    
    @staticmethod
    def _get_request_data():
        data = {}
        if request.args:
            data.update(request.args.to_dict(flat=True))
        if request.form:
            form_data = dict(request.form)
            for key, value in form_data.items():
                if isinstance(value, list) and len(value) == 1:
                    form_data[key] = value[0]
            data.update(form_data)
        elif request.is_json:
            payload = request.get_json() or {}
            if isinstance(payload, dict):
                data.update(payload)
        return data
    
    @staticmethod
    def dashboard_overview():
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            total_users = User.query.count()
            active_users = User.query.filter_by(is_active=True).count()
            total_hotels = Hotel.query.count()
            pending_hotels = Hotel.query.filter_by(status='pending').count()
            active_hotels = Hotel.query.filter_by(status='active').count()
            total_bookings = Booking.query.count()
            total_revenue = db.session.query(func.coalesce(func.sum(Booking.final_amount), 0)).filter(
                Booking.status == 'checked_out'
            ).scalar() or 0
            
            total_payments = Payment.query.count()
            total_reviews = Review.query.count()
            total_rooms = Room.query.count()
            
            avg_rating = db.session.query(func.coalesce(func.avg(Review.rating), 0)).filter(
                Review.rating.isnot(None)
            ).scalar() or 0
            
            recent_hotels = Hotel.query.order_by(Hotel.created_at.desc()).limit(5).all()
            recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
            
            return success_response(data={
                'summary': {
                    'total_users': total_users,
                    'active_users': active_users,
                    'total_hotels': total_hotels,
                    'pending_hotels': pending_hotels,
                    'active_hotels': active_hotels,
                    'total_bookings': total_bookings,
                    'total_revenue': float(total_revenue),
                    'total_payments': total_payments,
                    'total_reviews': total_reviews,
                    'total_rooms': total_rooms,
                    'avg_rating': float(avg_rating) if avg_rating else 0.0
                },
                'recent_hotels': [hotel.to_dict() for hotel in recent_hotels],
                'recent_users': [user.to_dict() for user in recent_users]
            })
        except Exception as exc:
            return error_response(f'Lỗi khi lấy thống kê: {str(exc)}', 500)
    
    @staticmethod
    def get_all_users():
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            
            query = User.query.order_by(User.created_at.desc())
            total = query.count()
            users = query.offset((page - 1) * per_page).limit(per_page).all()
            
            users_data = []
            for u in users:
                user_dict = u.to_dict()
                user_dict['username'] = u.email.split('@')[0]
                users_data.append(user_dict)
            
            return success_response(data={
                'users': users_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
        except Exception as exc:
            return error_response(f'Lỗi khi lấy danh sách người dùng: {str(exc)}', 500)
    
    @staticmethod
    def create_user():
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            data = AdminController._get_request_data()
            if not data:
                return error_response('Yêu cầu phải có dữ liệu', 400)
            
            schema = AdminUserCreateSchema()
            validated_data = schema.load(data)
            
            email = normalize_email(validated_data['email'])
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                return error_response('Email đã được sử dụng', 409)
            
            role = Role.query.get(validated_data['role_id'])
            if not role:
                return error_response('Không tìm thấy role', 404)
            
            new_user = User(
                email=email,
                full_name=validated_data['full_name'],
                phone=validated_data.get('phone'),
                address=validated_data.get('address'),
                id_card=validated_data.get('id_card'),
                role_id=validated_data['role_id'],
                is_active=validated_data.get('is_active', True),
                email_verified=validated_data.get('email_verified', False)
            )
            new_user.set_password(validated_data['password'])
            
            db.session.add(new_user)
            db.session.commit()
            
            return success_response(
                data={'user': new_user.to_dict()},
                message='Tạo người dùng thành công',
                status_code=201
            )
        except ValidationError as e:
            return validation_error_response(e.messages)
        except Exception as exc:
            db.session.rollback()
            return error_response(f'Lỗi khi tạo người dùng: {str(exc)}', 500)
    
    @staticmethod
    def get_user_detail(user_id):
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            target_user = User.query.get(user_id)
            if not target_user:
                return error_response('Không tìm thấy người dùng', 404)
            
            user_dict = target_user.to_dict()
            user_dict['bookings'] = [b.to_dict() for b in target_user.bookings[:10]]
            user_dict['reviews'] = [r.to_dict() for r in target_user.reviews[:10]]
            
            return success_response(data={'user': user_dict})
        except Exception as exc:
            return error_response(f'Lỗi khi lấy thông tin người dùng: {str(exc)}', 500)
    
    @staticmethod
    def update_user_role(user_id):
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            data = AdminController._get_request_data()
            role_id = data.get('role_id', type=int)
            
            if not role_id:
                return error_response('Thiếu role_id', 400)
            
            target_user = User.query.get(user_id)
            if not target_user:
                return error_response('Không tìm thấy người dùng', 404)
            
            role = Role.query.get(role_id)
            if not role:
                return error_response('Không tìm thấy role', 404)
            
            target_user.role_id = role_id
            db.session.commit()
            
            return success_response(message='Cập nhật role thành công')
        except Exception as exc:
            db.session.rollback()
            return error_response(f'Lỗi khi cập nhật role: {str(exc)}', 500)
    
    @staticmethod
    def update_user_status(user_id):
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            data = AdminController._get_request_data()
            is_active = data.get('is_active')
            
            if is_active is None:
                return error_response('Thiếu is_active', 400)
            
            target_user = User.query.get(user_id)
            if not target_user:
                return error_response('Không tìm thấy người dùng', 404)
            
            target_user.is_active = bool(int(is_active)) if isinstance(is_active, str) else bool(is_active)
            db.session.commit()
            
            return success_response(message='Cập nhật trạng thái thành công')
        except Exception as exc:
            db.session.rollback()
            return error_response(f'Lỗi khi cập nhật trạng thái: {str(exc)}', 500)
    
    @staticmethod
    def delete_user(user_id):
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            target_user = User.query.get(user_id)
            if not target_user:
                return error_response('Không tìm thấy người dùng', 404)
            
            if target_user.role.role_name == 'admin':
                return error_response('Không thể xóa tài khoản admin', 400)
            
            db.session.delete(target_user)
            db.session.commit()
            
            return success_response(message='Xóa người dùng thành công')
        except Exception as exc:
            db.session.rollback()
            return error_response(f'Lỗi khi xóa người dùng: {str(exc)}', 500)
    
    @staticmethod
    def get_all_hotels():
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            
            query = Hotel.query.order_by(Hotel.created_at.desc())
            total = query.count()
            hotels = query.offset((page - 1) * per_page).limit(per_page).all()
            
            hotels_data = []
            for hotel in hotels:
                hotel_dict = hotel.to_dict()
                hotel_dict['images'] = [img.to_dict() for img in hotel.images] if hotel.images else []
                hotels_data.append(hotel_dict)
            
            return success_response(data={
                'hotels': hotels_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
        except Exception as exc:
            return error_response(f'Lỗi khi lấy danh sách khách sạn: {str(exc)}', 500)
    
    @staticmethod
    def get_pending_hotels():
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            
            query = Hotel.query.filter_by(status='pending').order_by(Hotel.created_at.desc())
            total = query.count()
            hotels = query.offset((page - 1) * per_page).limit(per_page).all()
            
            hotels_data = []
            for hotel in hotels:
                hotel_dict = hotel.to_dict()
                hotel_dict['images'] = [img.to_dict() for img in hotel.images] if hotel.images else []
                hotels_data.append(hotel_dict)
            
            return success_response(data={
                'hotels': hotels_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
        except Exception as exc:
            return error_response(f'Lỗi khi lấy danh sách khách sạn chờ duyệt: {str(exc)}', 500)
    
    @staticmethod
    def approve_hotel(hotel_id):
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            hotel = Hotel.query.get(hotel_id)
            if not hotel:
                return error_response('Không tìm thấy khách sạn', 404)
            
            hotel.status = 'active'
            db.session.commit()
            
            return success_response(message='Phê duyệt khách sạn thành công')
        except Exception as exc:
            db.session.rollback()
            return error_response(f'Lỗi khi phê duyệt khách sạn: {str(exc)}', 500)
    
    @staticmethod
    def reject_hotel(hotel_id):
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            hotel = Hotel.query.get(hotel_id)
            if not hotel:
                return error_response('Không tìm thấy khách sạn', 404)
            
            hotel.status = 'rejected'
            db.session.commit()
            
            return success_response(message='Từ chối khách sạn thành công')
        except Exception as exc:
            db.session.rollback()
            return error_response(f'Lỗi khi từ chối khách sạn: {str(exc)}', 500)
    
    @staticmethod
    def toggle_hotel_featured(hotel_id):
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            data = AdminController._get_request_data()
            is_featured = data.get('is_featured')
            
            hotel = Hotel.query.get(hotel_id)
            if not hotel:
                return error_response('Không tìm thấy khách sạn', 404)
            
            hotel.is_featured = bool(int(is_featured)) if isinstance(is_featured, str) else bool(is_featured)
            db.session.commit()
            
            return success_response(message='Cập nhật featured thành công')
        except Exception as exc:
            db.session.rollback()
            return error_response(f'Lỗi khi cập nhật featured: {str(exc)}', 500)
    
    @staticmethod
    def suspend_hotel(hotel_id):
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            hotel = Hotel.query.get(hotel_id)
            if not hotel:
                return error_response('Không tìm thấy khách sạn', 404)
            
            hotel.status = 'suspended'
            db.session.commit()
            
            return success_response(message='Đình chỉ khách sạn thành công')
        except Exception as exc:
            db.session.rollback()
            return error_response(f'Lỗi khi đình chỉ khách sạn: {str(exc)}', 500)
    
    @staticmethod
    def get_all_bookings():
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            
            query = Booking.query.order_by(Booking.created_at.desc())
            total = query.count()
            bookings = query.offset((page - 1) * per_page).limit(per_page).all()
            
            bookings_data = []
            for booking in bookings:
                booking_dict = booking.to_dict()
                booking_dict['hotel'] = booking.hotel.to_dict() if booking.hotel else None
                booking_dict['user'] = booking.user.to_dict() if booking.user else None
                bookings_data.append(booking_dict)
            
            return success_response(data={
                'bookings': bookings_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
        except Exception as exc:
            return error_response(f'Lỗi khi lấy danh sách booking: {str(exc)}', 500)
    
    @staticmethod
    def get_all_payments():
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            
            query = Payment.query.order_by(Payment.created_at.desc())
            total = query.count()
            payments = query.offset((page - 1) * per_page).limit(per_page).all()
            
            payments_data = []
            for payment in payments:
                payment_dict = payment.to_dict()
                payment_dict['booking'] = payment.booking.to_dict() if payment.booking else None
                payments_data.append(payment_dict)
            
            return success_response(data={
                'payments': payments_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
        except Exception as exc:
            return error_response(f'Lỗi khi lấy danh sách thanh toán: {str(exc)}', 500)
    
    @staticmethod
    def get_all_reviews():
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            
            query = Review.query.order_by(Review.created_at.desc())
            total = query.count()
            reviews = query.offset((page - 1) * per_page).limit(per_page).all()
            
            reviews_data = []
            for review in reviews:
                review_dict = review.to_dict()
                review_dict['hotel'] = review.hotel.to_dict() if review.hotel else None
                review_dict['user'] = review.user.to_dict() if review.user else None
                reviews_data.append(review_dict)
            
            return success_response(data={
                'reviews': reviews_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
        except Exception as exc:
            return error_response(f'Lỗi khi lấy danh sách đánh giá: {str(exc)}', 500)
    
    @staticmethod
    def hide_review(review_id):
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            review = Review.query.get(review_id)
            if not review:
                return error_response('Không tìm thấy đánh giá', 404)
            
            review.status = 'hidden'
            db.session.commit()
            
            return success_response(message='Ẩn đánh giá thành công')
        except Exception as exc:
            db.session.rollback()
            return error_response(f'Lỗi khi ẩn đánh giá: {str(exc)}', 500)
    
    @staticmethod
    def delete_review(review_id):
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            review = Review.query.get(review_id)
            if not review:
                return error_response('Không tìm thấy đánh giá', 404)
            
            db.session.delete(review)
            db.session.commit()
            
            return success_response(message='Xóa đánh giá thành công')
        except Exception as exc:
            db.session.rollback()
            return error_response(f'Lỗi khi xóa đánh giá: {str(exc)}', 500)
    
    @staticmethod
    def get_all_roles():
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            
            query = Role.query.order_by(Role.created_at.desc())
            total = query.count()
            roles = query.offset((page - 1) * per_page).limit(per_page).all()
            roles_data = [role.to_dict() for role in roles]
            
            return success_response(data={
                'roles': roles_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
        except Exception as exc:
            return error_response(f'Lỗi khi lấy danh sách roles: {str(exc)}', 500)
    
    @staticmethod
    def create_role():
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            data = AdminController._get_request_data()
            role_name = data.get('role_name')
            description = data.get('description')
            
            if not role_name:
                return error_response('Thiếu role_name', 400)
            
            existing = Role.query.filter_by(role_name=role_name).first()
            if existing:
                return error_response('Role đã tồn tại', 400)
            
            role = Role(role_name=role_name, description=description)
            db.session.add(role)
            db.session.commit()
            
            return success_response(message='Tạo role thành công')
        except Exception as exc:
            db.session.rollback()
            return error_response(f'Lỗi khi tạo role: {str(exc)}', 500)
    
    @staticmethod
    def delete_role(role_id):
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            role = Role.query.get(role_id)
            if not role:
                return error_response('Không tìm thấy role', 404)
            
            if role.role_name in ['admin', 'user', 'hotel_owner']:
                return error_response('Không thể xóa role hệ thống', 400)
            
            db.session.delete(role)
            db.session.commit()
            
            return success_response(message='Xóa role thành công')
        except Exception as exc:
            db.session.rollback()
            return error_response(f'Lỗi khi xóa role: {str(exc)}', 500)
    
    @staticmethod
    def export_report():
        user, error = AdminController._require_admin()
        if error:
            return error
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'admin_report_{timestamp}.csv'
            
            output = []
            
            output.append(['BÁO CÁO TỔNG QUAN HỆ THỐNG'])
            output.append(['Ngày xuất báo cáo:', datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
            output.append([])
            
            total_users = User.query.count()
            active_users = User.query.filter_by(is_active=True).count()
            total_hotels = Hotel.query.count()
            pending_hotels = Hotel.query.filter_by(status='pending').count()
            active_hotels = Hotel.query.filter_by(status='active').count()
            total_bookings = Booking.query.count()
            total_payments = Payment.query.count()
            total_reviews = Review.query.count()
            total_rooms = Room.query.count()
            
            total_revenue = db.session.query(func.coalesce(func.sum(Booking.final_amount), 0)).filter(
                Booking.status == 'checked_out'
            ).scalar() or 0
            
            avg_rating = db.session.query(func.coalesce(func.avg(Review.rating), 0)).filter(
                Review.rating.isnot(None)
            ).scalar() or 0
            
            output.append(['THỐNG KÊ TỔNG QUAN'])
            output.append(['Tổng người dùng', total_users])
            output.append(['Người dùng đang hoạt động', active_users])
            output.append(['Tổng khách sạn', total_hotels])
            output.append(['Khách sạn đang hoạt động', active_hotels])
            output.append(['Khách sạn chờ duyệt', pending_hotels])
            output.append(['Tổng booking', total_bookings])
            output.append(['Tổng thanh toán', total_payments])
            output.append(['Tổng đánh giá', total_reviews])
            output.append(['Tổng phòng', total_rooms])
            output.append(['Doanh thu tổng', f'{float(total_revenue):,.0f} VNĐ'])
            output.append(['Đánh giá trung bình', f'{float(avg_rating):.1f}/5'])
            output.append([])
            
            output.append(['CHI TIẾT BOOKING'])
            output.append(['ID', 'Khách sạn', 'Người dùng', 'Check-in', 'Check-out', 'Trạng thái', 'Số tiền'])
            bookings = Booking.query.order_by(Booking.created_at.desc()).limit(100).all()
            for booking in bookings:
                hotel_name = booking.hotel.hotel_name if booking.hotel else 'N/A'
                user_email = booking.user.email if booking.user else 'N/A'
                output.append([
                    booking.booking_id,
                    hotel_name,
                    user_email,
                    booking.check_in_date.strftime('%d/%m/%Y') if booking.check_in_date else 'N/A',
                    booking.check_out_date.strftime('%d/%m/%Y') if booking.check_out_date else 'N/A',
                    booking.status,
                    f'{float(booking.final_amount):,.0f}' if booking.final_amount else '0'
                ])
            output.append([])
            
            output.append(['CHI TIẾT THANH TOÁN'])
            output.append(['ID', 'Booking ID', 'Phương thức', 'Số tiền', 'Trạng thái', 'Ngày thanh toán'])
            payments = Payment.query.order_by(Payment.created_at.desc()).limit(100).all()
            for payment in payments:
                output.append([
                    payment.payment_id,
                    payment.booking_id,
                    payment.payment_method,
                    f'{float(payment.amount):,.0f}' if payment.amount else '0',
                    payment.payment_status,
                    payment.payment_date.strftime('%d/%m/%Y %H:%M') if payment.payment_date else 'N/A'
                ])
            
            import io
            output_buffer = io.StringIO()
            writer = csv.writer(output_buffer)
            for row in output:
                writer.writerow(row)
            
            csv_data = output_buffer.getvalue()
            output_buffer.close()
            
            response = Response(
                csv_data.encode('utf-8-sig'),
                mimetype='text/csv; charset=utf-8-sig',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Type': 'text/csv; charset=utf-8-sig'
                }
            )
            
            return response
        except Exception as exc:
            return error_response(f'Lỗi khi xuất báo cáo: {str(exc)}', 500)

