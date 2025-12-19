from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.controllers.admin_controller import AdminController
from app.utils.decorators import role_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _extract_payload(result):
    try:
        return result[0].get_json()
    except Exception:
        return {}


def _render_template(result, template, **context):
    payload = _extract_payload(result)
    error = payload.get('message') if result[1] >= 400 else None
    success = payload.get('message') if result[1] < 400 else None
    return render_template(template, result=result, error=error, success=success, **context)


def _redirect_with_params(endpoint='admin.admin_dashboard'):
    params = request.args.to_dict(flat=True)
    return redirect(url_for(endpoint, **params))


@admin_bp.route('/dashboard', methods=['GET'])
@role_required('admin')
def admin_dashboard():
    result = AdminController.dashboard_overview()
    return _render_template(result, 'admin/dashboard.html')


@admin_bp.route('/users', methods=['GET'])
@role_required('admin')
def admin_users():
    result = AdminController.get_all_users()
    return _render_template(result, 'admin/users.html')


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@role_required('admin')
def admin_users_create():
    if request.method == 'POST':
        result = AdminController.create_user()
        if result[1] < 400:
            flash('Tạo người dùng thành công', 'success')
            return redirect(url_for('admin.admin_users'))
        else:
            payload = _extract_payload(result)
            flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
    
    roles_result = AdminController.get_all_roles()
    roles_payload = _extract_payload(roles_result)
    roles = roles_payload.get('data', {}).get('roles', []) if roles_payload else []
    return _render_template(({}, 200), 'admin/user_create.html', roles=roles)


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@role_required('admin')
def admin_user_detail(user_id):
    result = AdminController.get_user_detail(user_id)
    return _render_template(result, 'admin/user_detail.html', user_id=user_id)


@admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
@role_required('admin')
def admin_user_role(user_id):
    result = AdminController.update_user_role(user_id)
    if result[1] < 400:
        flash('Cập nhật role thành công', 'success')
    else:
        payload = _extract_payload(result)
        flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
    return redirect(url_for('admin.admin_user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/status', methods=['POST'])
@role_required('admin')
def admin_user_status(user_id):
    result = AdminController.update_user_status(user_id)
    if result[1] < 400:
        flash('Cập nhật trạng thái thành công', 'success')
    else:
        payload = _extract_payload(result)
        flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
    return redirect(url_for('admin.admin_user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@role_required('admin')
def admin_user_delete(user_id):
    result = AdminController.delete_user(user_id)
    if result[1] < 400:
        flash('Xóa người dùng thành công', 'success')
        return redirect(url_for('admin.admin_users'))
    else:
        payload = _extract_payload(result)
        flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
        return redirect(url_for('admin.admin_user_detail', user_id=user_id))


@admin_bp.route('/hotels', methods=['GET'])
@role_required('admin')
def admin_hotels():
    result = AdminController.get_all_hotels()
    return _render_template(result, 'admin/hotels.html')


@admin_bp.route('/hotels/pending', methods=['GET'])
@role_required('admin')
def admin_hotels_pending():
    result = AdminController.get_pending_hotels()
    return _render_template(result, 'admin/hotels_pending.html')


@admin_bp.route('/hotels/<int:hotel_id>/approve', methods=['POST'])
@role_required('admin')
def admin_hotels_approve(hotel_id):
    result = AdminController.approve_hotel(hotel_id)
    if result[1] < 400:
        flash('Phê duyệt khách sạn thành công', 'success')
    else:
        payload = _extract_payload(result)
        flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
    return redirect(url_for('admin.admin_hotels_pending'))


@admin_bp.route('/hotels/<int:hotel_id>/reject', methods=['POST'])
@role_required('admin')
def admin_hotels_reject(hotel_id):
    result = AdminController.reject_hotel(hotel_id)
    if result[1] < 400:
        flash('Từ chối khách sạn thành công', 'success')
    else:
        payload = _extract_payload(result)
        flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
    return redirect(url_for('admin.admin_hotels_pending'))


@admin_bp.route('/hotels/<int:hotel_id>/featured', methods=['POST'])
@role_required('admin')
def admin_hotels_featured(hotel_id):
    result = AdminController.toggle_hotel_featured(hotel_id)
    if result[1] < 400:
        flash('Cập nhật featured thành công', 'success')
    else:
        payload = _extract_payload(result)
        flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
    return redirect(url_for('admin.admin_hotels'))


@admin_bp.route('/hotels/<int:hotel_id>/suspend', methods=['POST'])
@role_required('admin')
def admin_hotels_suspend(hotel_id):
    result = AdminController.suspend_hotel(hotel_id)
    if result[1] < 400:
        flash('Đình chỉ khách sạn thành công', 'success')
    else:
        payload = _extract_payload(result)
        flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
    return redirect(url_for('admin.admin_hotels'))


@admin_bp.route('/bookings', methods=['GET'])
@role_required('admin')
def admin_bookings():
    result = AdminController.get_all_bookings()
    return _render_template(result, 'admin/bookings.html')


@admin_bp.route('/payments', methods=['GET'])
@role_required('admin')
def admin_payments():
    result = AdminController.get_all_payments()
    return _render_template(result, 'admin/payments.html')


@admin_bp.route('/reviews', methods=['GET'])
@role_required('admin')
def admin_reviews():
    result = AdminController.get_all_reviews()
    return _render_template(result, 'admin/reviews.html')


@admin_bp.route('/reviews/<int:review_id>/hide', methods=['POST'])
@role_required('admin')
def admin_review_hide(review_id):
    result = AdminController.hide_review(review_id)
    if result[1] < 400:
        flash('Ẩn đánh giá thành công', 'success')
    else:
        payload = _extract_payload(result)
        flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
    return redirect(url_for('admin.admin_reviews'))


@admin_bp.route('/reviews/<int:review_id>/delete', methods=['POST'])
@role_required('admin')
def admin_review_delete(review_id):
    result = AdminController.delete_review(review_id)
    if result[1] < 400:
        flash('Xóa đánh giá thành công', 'success')
    else:
        payload = _extract_payload(result)
        flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
    return redirect(url_for('admin.admin_reviews'))


@admin_bp.route('/roles', methods=['GET'])
@role_required('admin')
def admin_roles():
    result = AdminController.get_all_roles()
    return _render_template(result, 'admin/roles.html')


@admin_bp.route('/roles/create', methods=['POST'])
@role_required('admin')
def admin_roles_create():
    result = AdminController.create_role()
    if result[1] < 400:
        flash('Tạo role thành công', 'success')
    else:
        payload = _extract_payload(result)
        flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
    return redirect(url_for('admin.admin_roles'))


@admin_bp.route('/roles/<int:role_id>/delete', methods=['POST'])
@role_required('admin')
def admin_roles_delete(role_id):
    result = AdminController.delete_role(role_id)
    if result[1] < 400:
        flash('Xóa role thành công', 'success')
    else:
        payload = _extract_payload(result)
        flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
    return redirect(url_for('admin.admin_roles'))


@admin_bp.route('/export-report', methods=['POST'])
@role_required('admin')
def admin_export_report():
    result = AdminController.export_report()
    if isinstance(result, tuple) and result[1] >= 400:
        payload = _extract_payload(result)
        flash(payload.get('message', 'Có lỗi xảy ra'), 'error')
        return redirect(url_for('admin.admin_dashboard'))
    return result

