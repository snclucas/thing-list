from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user

from database_functions import get_user_locations, update_location_by_id, find_location, add_new_location, \
    delete_location_from_db
from models import Location

location = Blueprint('location', __name__)


@location.route('/locations')
@login_required
def locations():
    user_locations = get_user_locations(user=current_user)
    return render_template('location/locations.html', name=current_user.username, locations=user_locations)


@location.route('/location/<location_id>/delete')
@login_required
def delete_location(location_id):
    delete_location_from_db(user=current_user, location_id=location_id)
    return redirect(url_for('location.locations'))


@location.route('/location/add', methods=['POST'])
@login_required
def add_location():

    if request.method == 'POST':
        location_id = request.form.get("location_id")
        location_name = request.form.get("location_name")
        location_description = request.form.get("location_description")

        new_location_data = {
            "id": location_id,
            "name": location_name,
            "description": location_description,
        }

        potential_location = find_location(location_id=int(location_id))

        if potential_location is None:
            location_ = Location(name=new_location_data['name'], description=new_location_data['description'])
            add_new_location(location_name=location_name,
                             location_description=location_description, to_user=current_user)
        else:
            update_location_by_id(location_data=new_location_data, user=current_user)

        return redirect(url_for('location.locations'))
