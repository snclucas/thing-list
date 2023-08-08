import bleach
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from database_functions import get_user_locations, update_location_by_id, get_or_add_new_location, \
    delete_location, find_location_by_id
from models import Location

location = Blueprint('location', __name__)


@location.route('/locations', methods=['GET'])
@login_required
def locations():
    user_locations = get_user_locations(user_id=current_user.id)
    return render_template('location/locations.html', username=current_user.username, locations=user_locations)


@location.route('/location/delete', methods=['POST'])
@login_required
def del_location():
    if request.method == 'POST':
        json_data = request.json
        location_id = json_data["location_id"]
        delete_location(user_id=current_user.id, location_id=int(location_id))
    return redirect(url_for('location.locations'))


@location.route('/location/add', methods=['POST'])
@login_required
def add_location():

    if request.method == 'POST':
        location_id = request.form.get("location_id")
        location_name = request.form.get("location_name")
        location_description = request.form.get("location_description")

        # sanitize the inputs
        location_name = bleach.clean(location_name)
        location_description = bleach.clean(location_description)

        new_location_data = {
            "id": location_id,
            "name": location_name,
            "description": location_description,
        }

        potential_location = find_location_by_id(location_id=int(location_id))

        if potential_location is None:
            get_or_add_new_location(location_name=location_name,
                                    location_description=location_description, to_user_id=current_user.id)
        else:
            update_location_by_id(location_data=new_location_data, user=current_user)

        return redirect(url_for('location.locations'))
