import bleach
from flask import Blueprint, render_template, redirect, url_for, request, abort, Response
from flask_login import login_required, current_user

from database_functions import find_template, add_new_template, update_template_by_id, get_user_templates, \
    delete_template_from_db, get_all_fields, save_template_fields
from models import FieldTemplate

field_template = Blueprint('field_template', __name__)


@field_template.route('/field-templates')
@login_required
def templates():
    return templates_with_username(username=current_user.username)


@field_template.route('/@<username>/field-templates')
@login_required
def templates_with_username(username):
    all_fields = dict(get_all_fields())
    user_templates = get_user_templates(user=current_user)
    return render_template('field_template/field_templates.html',
                           name=current_user.username, templates=user_templates, all_fields=all_fields)


@field_template.route('/set-template-fields', methods=['POST'])
@login_required
def set_template_fields():
    if request.method == 'POST':
        request_xhr_key = request.headers.get('X-Requested-With')
        if request_xhr_key and request_xhr_key == 'XMLHttpRequest':
            json_data = request.json
            template_name = json_data['template_name']

            # sanitise template name
            template_name = bleach.clean(template_name)

            field_ids = json_data['field_ids']
            if len(field_ids) == 0:
                abort(Response("At least 1 field is required for the template", 400))

            field_ids = [str(x) for x in field_ids]

            save_template_fields(template_name=template_name, fields=field_ids, user=current_user)

    return True


@field_template.route('/field-templates/delete', methods=['POST'])
@login_required
def delete_template():
    if request.method == 'POST':
        json_data = request.json
        template_id = json_data['template_id']
        delete_template_from_db(user=current_user, template_id=template_id)
        return redirect(url_for('field_template.templates'))


@field_template.route('/field-templates/add', methods=['POST'])
@login_required
def add_template():

    if request.method == 'POST':
        template_id = request.form.get("template_id")
        template_name = request.form.get("template_name")
        template_fields = request.form.get("template_fields")

        new_template_data = {
            "id": template_id,
            "name": template_name,
            "fields": template_fields,
        }

        potential_template = find_template(template_id=int(template_id))

        if potential_template is None:
            template_ = FieldTemplate(name=new_template_data['name'], fields=new_template_data['fields'])
            add_new_template(name=template_name,
                             fields=template_fields, to_user=current_user)
        else:
            update_template_by_id(template_data=new_template_data, user=current_user)

        return redirect(url_for('field_templates.templates'))
