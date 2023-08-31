import os
import pathlib
from typing import Union, List

import flask_bcrypt

from slugify import slugify
from sqlalchemy import select, and_, ClauseElement, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.functions import func

from app import db, app, __PUBLIC__, __OWNER__
from models import Inventory, User, Item, UserInventory, InventoryItem, ItemType, Tag, \
    Location, Image, ItemImage, Field, ItemField, FieldTemplate, Notification, TemplateField, Relateditems

_NONE_ = "None"


def drop_then_create():
    try:
        db.drop_all()
        db.create_all()
        db.session.commit()
    except Exception as e:
        print(e)


def post_user_add_hook(new_user: User):
    with app.app_context():
        add_user_inventory(name=f"__default__{new_user.username}", description=f"Default inventory",
                           public=False,
                           user_id=new_user.id)
        get_or_add_new_location(location_name=_NONE_, location_description="No location (default)",
                                to_user_id=new_user.id)
        add_new_user_itemtype(name=_NONE_, user_id=new_user.id)
    # add default locations, types


def backup_to_json():
    with app.app_context():
        backup_json = {}


# --- INVENTORIES ---


def add_user_inventory(name, description, public, user_id: int):
    ret = {}
    slug = slugify(name)

    with app.app_context():
        try:
            # add it initially private
            to_user = User.query.filter_by(id=user_id).first()
            new_inventory = Inventory(name=name, description=description, slug=slug, owner=to_user, public=public)

            if to_user is not None:
                db.session.expire_on_commit = False
                db.session.add(new_inventory)
                db.session.flush()
                ret["id"] = new_inventory.id
                to_user.inventories.append(new_inventory)
                db.session.commit()
                db.session.expunge_all()

                ret["name"] = name
                ret["description"] = description
                ret["slug"] = slug
                ret["public"] = public

                return ret, "success"

        except SQLAlchemyError as error:
            return None, "Could not add inventory"


def get_user_default_inventory(user_id: int):
    with app.app_context():
        # Find user default inventory
        user_ = find_user_by_id(user_id=user_id)
        user_default_inventory_ = Inventory.query.filter_by(name=f"__default__{user_.username}").filter_by().first()
        return user_default_inventory_


def delete_inventory_by_id(inventory_id: int, user_id: int):
    """
    If the User has Items within the Inventory - re-link Items to Users default Inventory via the ItemInventory table
    Delete the UserInventory for the user
    If there are no more UserInventory links to the Inventory - delete the Inventory
    """

    with app.app_context():
        # Get the user_inventory bu user_id and inventory_id
        user_inventory_ = UserInventory.query.filter_by(user_id=user_id).filter_by(inventory_id=inventory_id).first()

        if user_inventory_ is not None:
            # Find out if any other users point to this inventory, if not delete it
            inventory_id_to_delete = user_inventory_.inventory_id

            # Get the current user's default inventory
            user_default_inventory_ = get_user_default_inventory(user_id=user_id)

            inv_items_ = InventoryItem.query.filter_by(inventory_id=inventory_id_to_delete).all()
            for row in inv_items_:
                # Add the items that are in this inventory to the user's default
                row.inventory_id = user_default_inventory_.id

            # Delete the UserInventory for the user
            db.session.delete(user_inventory_)
            db.session.commit()

            users_invs_ = UserInventory.query.filter_by(inventory_id=inventory_id_to_delete).all()
            if len(users_invs_) == 0:
                # remove the actual inventory
                inv_ = Inventory.query.filter_by(id=inventory_id_to_delete).first()
                if inv_ is not None:
                    db.session.delete(inv_)
                    db.session.commit()


def delete_notification_by_id(notification_id: int, user: User):
    with app.app_context():
        notification_ = Notification.query.filter_by(id=notification_id).one_or_none()

        if notification_ is not None:
            user.notifications.remove(notification_)
            return {
                "success": True,
                "message": f"Removed notification with ID {notification_.id} from user @{user.username}"
            }

        return {
            "success": False,
            "message": f"No notification with ID {notification_id} for user @{user.username}"
        }


def get_item_custom_field_data(user_id: int, item_list=None):
    with app.app_context():
        item_field_data_ = db.session.query(Item.id, Field.field, ItemField.value) \
            .join(ItemField, ItemField.field_id == Field.id) \
            .join(Item, ItemField.item_id == Item.id) \
            .filter(Item.user_id == user_id)

        if item_list is not None:
            if isinstance(item_list, list):
                item_field_data_ = item_field_data_.filter(Item.id.in_(item_list))

        item_field_data_ = item_field_data_.all()

        sdsd = {}
        for row in item_field_data_:
            if row[0] in sdsd:
                sdsd[row[0]][row[1]] = row[2]
            else:
                sdsd[row[0]] = {row[1]: row[2]}

        return sdsd


def delete_item_type_from_db(itemtype_id: int, user: User) -> (bool, str):
    with app.app_context():
        itemtype_ = ItemType.query.filter_by(user_id=user.id).filter_by(id=itemtype_id).first()

        user_none_type_ = ItemType.query.filter_by(user_id=user.id).filter_by(name=_NONE_).first()

        if itemtype_ is not None:
            # find items with this item type
            d = Item.query.filter_by(user_id=user.id).filter_by(item_type=itemtype_id).all()
            for row in d:
                row.item_type = user_none_type_.id

            try:
                db.session.commit()
                db.session.delete(itemtype_)
                db.session.commit()
                return True, "Item type successfully deleted"
            except SQLAlchemyError:
                return False, "Error deleting item type"


def get_user_item_count(user_id: int):
    with app.app_context():
        item_count_ = db.session.query(Item).filter(Item.user_id == user_id).count()
        return item_count_


def _find_field_by_name(field_name: str):
    field_slug = slugify(field_name)
    field_ = Field.query.filter(Field.slug == field_slug).one_or_none()
    return field_


def _search_by_field_value(field_id: int, user_id: int, query: str):
    looking_for = '%{0}%'.format(query)
    with app.app_context():
        items_ = db.session.query(Item) \
            .join(ItemField, ItemField.item_id == Item.id) \
            .filter(ItemField.field_id == field_id) \
            .filter(ItemField.user_id == user_id) \
            .filter(ItemField.value.ilike(looking_for)).all()

        return items_


def search_items(query: str, user_id: int):
    items_arr = []
    with app.app_context():

        # see if there is a search modifier
        if ':' in query:
            search_modifier = query.split(':')[0]
            query = query.split(':')[1]

            if search_modifier.lower() == 'location':
                locations_ = Location.query\
                    .filter(Location.user_id == user_id)\
                    .filter(Location.name.like(query)).all()

                for location in locations_:
                    loc_id_ = location.id
                    items_ = Item.query.filter(or_(
                        Item.location_id == loc_id_,
                        Item.specific_location == query
                    )
                    ).all()

                    if len(items_) > 0:
                        for item in items_:
                            items_arr.append(item.__dict__)

                looking_for = '%{0}%'.format(query)
                items_ = Item.query.filter(
                    Item.specific_location.ilike(looking_for)
                ).all()

                if len(items_) > 0:
                    for item in items_:
                        items_arr.append(item.__dict__)

            elif search_modifier.lower() == 'tags':
                query = query.split(",")
                q_ = Item.query

                any_tags_found = False
                for tag_ in query:
                    tag_ = tag_.strip()
                    tag_ = tag_.replace(" ", "@#$")
                    t_ = find_tag(tag=tag_)

                    if t_ is not None:
                        any_tags_found = True
                        q_ = q_.filter(Item.tags.contains(t_))

                if any_tags_found:
                    items_ = q_.all()

                    if len(items_) > 0:
                        for item in items_:
                            items_arr.append(item.__dict__)

            elif search_modifier.lower() == 'type':
                query = query.split(",")

                types_ = ItemType.query \
                    .filter(ItemType.user_id == user_id) \
                    .filter(ItemType.name.like(query)).all()

                type_ids = []
                for type_ in types_:
                    type_ids.append(type_.id)

                items_ = Item.query.filter(Item.user_id == user_id).filter(Item.item_type.in_([type_ids])).all()

                if len(items_) > 0:
                    for item in items_:
                        items_arr.append(item.__dict__)

            else:  # we have a custom field
                field_ = _find_field_by_name(field_name=search_modifier)
                if field_ is not None:
                    field_id = field_.id
                    items_ = _search_by_field_value(field_id=field_id, user_id=user_id, query=query)

                    if len(items_) > 0:
                        for item in items_:
                            items_arr.append(item.__dict__)

        else:
            # search simple string
            looking_for = '%{0}%'.format(query)

            items_ = Item.query.filter(or_(
                Item.name.ilike(looking_for),
                Item.description.ilike(looking_for)
            )
            ).all()

            if len(items_) > 0:
                for item in items_:
                    items_arr.append(item.__dict__)

        return items_arr


def find_items(item_id=None, item_slug=None, inventory_id=None, item_type=None,
               item_tags=None, item_specific_location=None, item_location=None, logged_in_user=None,
               request_user=None):
    if logged_in_user is None:
        logged_in_user_id = None
    else:
        logged_in_user_id = logged_in_user.id

    if request_user is None:
        request_user_id = None
    else:
        request_user_id = request_user.id

    with app.app_context():

        if item_id is not None or item_slug is not None:
            d = db.session.query(Item, ItemType.name, Location.name,
                                 UserInventory, InventoryItem.access_level) \
                .join(InventoryItem, InventoryItem.item_id == Item.id) \
                .join(Inventory, Inventory.id == InventoryItem.inventory_id) \
                .join(ItemType, ItemType.id == Item.item_type) \
                .join(Location, Location.id == Item.location_id)

            if logged_in_user_id is None:
                if request_user_id is None:
                    d = d.filter(InventoryItem.access_level == __PUBLIC__)
                else:
                    d = d.filter(Item.user_id == request_user_id)
                    d = d.filter(InventoryItem.access_level == __PUBLIC__)

            else:
                if request_user_id is None:
                    d = d.filter(Item.user_id == logged_in_user_id)
                else:
                    if request_user_id != logged_in_user_id:
                        d = d.filter(Item.user_id == request_user_id)
                        d = d.filter(InventoryItem.access_level == __PUBLIC__)
                    else:
                        d = d.filter(Item.user_id == request_user_id)

            if item_id is not None:
                d = d.filter(Item.id == item_id)

            if item_slug is not None:
                d = d.filter(Item.slug == item_slug)

            return d.first()

        else:
            if inventory_id is not None and inventory_id != '':
                d = db.session.query(Item, ItemType.name, Location.name, InventoryItem.access_level) \
                    .join(ItemType, ItemType.id == Item.item_type) \
                    .join(Location, Location.id == Item.location_id)

                d = d.join(InventoryItem, InventoryItem.item_id == Item.id)
                d = d.join(Inventory, Inventory.id == InventoryItem.inventory_id)
                d = d.filter(InventoryItem.inventory_id == inventory_id)
            else:
                d = db.session.query(Item, ItemType.name, Location.name, InventoryItem.access_level) \
                    .join(ItemType, ItemType.id == Item.item_type) \
                    .join(Location, Location.id == Item.location_id)

                d = d.join(InventoryItem, InventoryItem.item_id == Item.id)

            if logged_in_user_id is None:
                if request_user_id is None:
                    d = d.filter(InventoryItem.access_level == 2)
                else:
                    d = d.filter(Item.user_id == request_user_id)
                    d = d.filter(InventoryItem.access_level == 2)

            else:
                if request_user_id is None:
                    d = d.filter(Item.user_id == logged_in_user_id)
                else:
                    if request_user_id != logged_in_user_id:
                        d = d.filter(Item.user_id == request_user_id)
                        d = d.filter(InventoryItem.access_level == 2)
                    else:
                        d = d.filter(Item.user_id == request_user_id)

            if item_type is not None and item_type != '':
                d = d.filter(Item.item_type == item_type)

            if item_location is not None and item_location != '':
                d = d.filter(Location.id == item_location)

            if item_specific_location is not None and item_specific_location != '':
                d = d.filter(Item.specific_location == item_specific_location)

            if item_tags is not None and item_tags != "":
                item_tags = item_tags.split(",")

                for tag_ in item_tags:
                    tag_ = tag_.strip()
                    tag_ = tag_.replace(" ", "@#$")
                    t_ = find_tag(tag=tag_)

                    if t_ is not None:
                        d = d.filter(Item.tags.contains(t_))

        sd = d.all()

        return sd


def change_item_access_level(item_ids: int, access_level: int, user_id: int):
    if not isinstance(item_ids, list):
        item_ids = [item_ids]

    with app.app_context():
        d = db.session.query(Item, InventoryItem) \
            .join(InventoryItem, InventoryItem.item_id == Item.id) \
            .join(Inventory, Inventory.id == InventoryItem.inventory_id) \
            .join(UserInventory, UserInventory.user_id == Item.user_id) \
            .filter(Item.id.in_(item_ids)) \
            .filter(Item.user_id == user_id)

        results_ = d.all()
        for item_, inventory_item_ in results_:
            inventory_item_.access_level = access_level

        db.session.commit()


def add_user(username: str, email: str, password: str) -> User:
    with app.app_context():
        password_hash = flask_bcrypt.generate_password_hash(password)
        user = User(username=username, email=email, password=password_hash, activated=True)
        db.session.add(user)
        db.session.commit()
        post_user_add_hook(new_user=user)
        return user


def get_all_user_locations(user: User) -> list[Location]:
    user_locations_ = Location.query.filter_by(user_id=user.id).all()
    return user_locations_


def get_all_user_tags(user_id: int) -> list[Tag]:
    with app.app_context():
        res_ = db.session.query(Tag).filter(Tag.user_id == user_id).all()
    return res_


def get_all_item_types() -> list:
    item_types_ = ItemType.query.all()
    return item_types_


def get_item_types(item_id=None, user_id=None) -> list:
    item_types_ = ItemType.query
    if item_id is not None:
        item_types_ = item_types_.filter_by(item_id=item_id)

    if user_id is not None:
        item_types_ = item_types_.filter_by(user_id=user_id)
    return item_types_.all()


def add_new_user_itemtype(name: str, user_id: int):
    with app.app_context():
        item_type_ = find_type_by_text(type_text=name, user_id=user_id)

        if item_type_ is None:
            new_item_type_ = ItemType(name=name.lower(), user_id=user_id)
            db.session.add(new_item_type_)
            db.session.commit()


def find_user(username_or_email: str) -> User:
    user = User.query.filter_by(username=username_or_email).first()
    if not user:
        user = User.query.filter_by(email=username_or_email).first()
    return user


def find_type_by_text(type_text: str, user_id: int = None) -> Union[dict, None]:
    with app.app_context():

        if user_id is None:
            item_type_ = ItemType.query.filter_by(name=type_text.lower().strip()).one_or_none()
        else:
            item_type_ = ItemType.query.filter_by(name=type_text.lower().strip()) \
                .filter_by(user_id=user_id).one_or_none()

        if item_type_ is not None:
            return {"id": item_type_.id, "name": item_type_.name, "user_id": item_type_.user_id}

        return None


def get_all_itemtypes_for_user(user_id: int, string_list=True) -> list:
    if string_list:
        stmt = select(ItemType.name) \
            .where(ItemType.user_id == user_id)
    else:
        stmt = select(ItemType) \
            .where(ItemType.user_id == user_id)

    res = db.session.execute(stmt).all()

    ret_data = []
    if res is not None:
        for row in res:
            ret_data.append(row[0])

    return ret_data


def find_user_by_username(username: str) -> User:
    user = User.query.filter_by(username=username).first()
    return user


def find_user_by_email(email: str) -> User:
    user = User.query.filter_by(email=email).first()
    return user


def find_user_by_token(token: str) -> User:
    user = User.query.filter_by(token=token).first()
    return user


def find_user_by_id(user_id: int) -> User:
    with app.app_context():
        user_ = db.session.query(User).filter(User.id == user_id).one()
        db.session.flush()
        db.session.expunge_all()
        db.session.close()
        return user_


def save_new_user(user_: User):
    with app.app_context():
        potential_user_ = find_user_by_username(username=user_.username)
        if potential_user_ is not None:
            return False, "Username taken"

        potential_user_ = find_user_by_email(email=user_.email)
        if potential_user_ is not None:
            return False, "Username taken"

        db.session.add(user_)
        db.session.commit()

        post_user_add_hook(new_user=user_)
        return True, "success"


def activate_user_in_db(user_id: int):
    with app.app_context():
        user_ = db.session.query(User).filter(User.id == user_id).one()
        user_.activated = True
        db.session.commit()


def find_item(item_id: int, user_id: int = None) -> Item:
    if user_id is None:
        item_ = Item.query.filter_by(id=item_id).first()
    else:
        item_ = Item.query.filter_by(id=item_id).filter_by(user_id=user_id).first()
    return item_


def find_item_by_slug(item_slug: int, user_id: int = None) -> Item:
    if user_id is None:
        item_ = Item.query.filter_by(slug=item_slug).first()
    else:
        item_ = Item.query.filter_by(slug=item_slug).filter_by(user_id=user_id).first()
    return item_


def find_tag(tag: str) -> User:
    tag_ = Tag.query.filter_by(tag=tag).first()
    return tag_


def find_location_by_id(location_id: int) -> Union[dict, None]:
    location_ = Location.query.filter_by(id=location_id).one_or_none()
    if location_ is not None:
        return location_.__dict__
    return None


def find_template(template_id: int) -> Location:
    template_ = FieldTemplate.query.filter_by(id=template_id).first()
    return template_


def find_location_by_name(location_name: str) -> Location:
    location_ = Location.query.filter_by(name=location_name).first()
    return location_


def find_inventory(inventory_id: int) -> Inventory:
    inventory_ = Inventory.query.filter_by(id=inventory_id).first()
    return inventory_


def find_inventory_by_id(inventory_id: int, user_id: int) -> (Inventory, UserInventory):
    inventory_ = Inventory.query.filter_by(id=inventory_id).first()
    user_inventory_ = UserInventory.query \
        .filter_by(inventory_id=inventory_.id).filter_by(user_id=user_id).first()
    return inventory_, user_inventory_


def find_inventory_by_slug(inventory_slug: str, user_id: int = None) -> (Inventory, UserInventory):
    # if user is None then they are not logged in

    user_is_logged_in = (user_id is not None)

    if user_is_logged_in:
        stmt = select(UserInventory, Inventory) \
            .join(UserInventory) \
            .join(User) \
            .where(UserInventory.user_id == user_id) \
            .where(Inventory.slug == inventory_slug)

        res = db.session.execute(stmt).first()
        if res is not None:
            user_inventory_, inventory_ = res[0], res[1]
        else:
            user_inventory_, inventory_ = None, None

    else:  # get the inventory if it is public
        stmt = db.session.query(Inventory) \
            .filter(Inventory.public == 1) \
            .filter(Inventory.slug == inventory_slug)

        res = db.session.execute(stmt).first()
        if res is not None:
            user_inventory_, inventory_ = None, res[0]
        else:
            user_inventory_, inventory_ = None, None

    return inventory_, user_inventory_


def unrelate_items_by_id(item1_id, item2_id):
    with app.app_context():
        item1_ = Item.query.filter(Item.id == item1_id).one_or_none()
        item2_ = Item.query.filter(Item.id == item2_id).one_or_none()
        if item1_ is not None and item2_ is not None:
            item1_.related_items.remove(item2_)
            db.session.commit()
            item2_.related_items.remove(item1_)
            db.session.commit()


def relate_items_by_id(item1_id, item2_id):
    with app.app_context():
        item1_ = Item.query.filter(Item.id == item1_id).one_or_none()
        item2_ = Item.query.filter(Item.id == item2_id).one_or_none()
        if item1_ is not None and item2_ is not None:
            item1_.related_items.append(item2_)
            item2_.related_items.append(item1_)
            db.session.commit()


def add_item_inventory(item, inventory):
    with app.app_context():
        stmt = select(Item).where(Item.id == item)
        item_ = db.session.execute(stmt).first()

        stmt = select(Inventory).where(Inventory.id == inventory)
        inventory_ = db.session.execute(stmt).first()

        inventory_[0].items.append(item_[0])
        db.session.commit()


def set_item_main_image(main_image_url, item_id, user: User):
    with app.app_context():
        item_ = find_item(item_id=item_id, user_id=user.id)
        if item_ is not None:
            item_.main_image = main_image_url

        db.session.commit()


def add_images_to_item(item_id, filenames, user: User):
    with app.app_context():
        item_ = find_item(item_id=item_id)
        for file in filenames:
            new_image = Image(image_filename=file, user_id=user.id)
            item_.images.append(new_image)

        item_.main_image = item_.images[0].image_filename

        db.session.commit()


def find_image(image_id: int, user: User) -> Image:
    image_ = Image.query.filter_by(id=image_id).filter_by(user_id=user.id).first()
    return image_


def final_all_user_inventories(user: User):
    stmt = select(UserInventory, Inventory) \
        .join(UserInventory) \
        .join(User) \
        .where(UserInventory.user_id == user.id)

    result = db.session.execute(stmt).all()
    return result


def delete_images_from_item(item_id, image_ids, user: User):
    with app.app_context():
        item_ = find_item(item_id=item_id)

        for image_id in image_ids:
            image_ = find_image(image_id=image_id, user=user)

            if image_ in item_.images:
                if image_.image_filename == item_.main_image:
                    item_.main_image = None
                item_.images.remove(image_)

                try:
                    os.remove(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], image_.image_filename))
                except OSError as er:
                    pass

        if item_.main_image is None:
            if len(item_.images) == 0:
                item_.main_image = None
            else:
                item_.main_image = item_.images[0].image_filename

        db.session.commit()


def update_template_by_id(template_data, user):
    with app.app_context():
        template_id = template_data['id']

        template_ = FieldTemplate.query.filter_by(id=template_id).filter_by(user_id=user.id).one()

        template_.name = template_data['name']
        template_.fields = template_data['fields']

        db.session.commit()


def update_location_by_id(location_data, user):
    with app.app_context():
        location_id = location_data['id']

        location_ = Location.query.filter_by(id=location_id).filter_by(user_id=user.id)

        location_.name = location_data['name']
        location_.description = location_data['description']

        db.session.commit()


def update_item_by_id(item_data: dict, item_id: int, user: User):
    with app.app_context():
        db.session.expire_on_commit = False

        stmt = select(Item) \
            .join(User) \
            .where(User.id == user.id) \
            .where(Item.id == item_id)
        r = db.session.execute(stmt).first()

        r[0].name = item_data['name']
        new_item_slug = f"{str(r[0].id)}-{slugify(item_data['name'])}"
        r[0].slug = new_item_slug
        r[0].description = item_data['description']
        r[0].quantity = item_data['item_quantity']
        r[0].location_id = item_data['item_location']
        r[0].specific_location = item_data['item_specific_location']

        item_tags = item_data['item_tags']
        if not isinstance(item_tags, list):
            item_tags = item_tags.strip()
            item_tags = item_tags.replace(" ", "@#$")
            if "," in item_tags:
                item_tags_list = item_tags.split(",")
        else:
            item_tags_list = item_tags

        r[0].tags = []
        for tag in item_tags_list:
            instance = db.session.query(Tag).filter_by(tag=tag).one_or_none()
            if not instance:
                instance = Tag(tag=tag, user_id=user.id)

            r[0].tags.append(instance)

        stmt2 = select(ItemType).where(ItemType.name == item_data['item_type'])
        r2 = db.session.execute(stmt2).first()

        if r2 is None:
            new_itemtype_ = ItemType(name=item_data['item_type'], user_id=user.id)
            db.session.add(new_itemtype_)
            db.session.flush()
            r[0].item_type = new_itemtype_.id
        else:
            r[0].item_type = r2[0].id

        db.session.commit()

        return new_item_slug


def delete_items(item_ids: list, user: User):
    with app.app_context():

        stmt = select(Item).join(User) \
            .where(Item.user_id == user.id) \
            .where(Item.id.in_(item_ids))
        items_ = db.session.execute(stmt).all()

        number_items_deleted = 0

        for item_ in items_:
            if item_[0] is not None:

                # remove related item relationships
                related_items_ = Relateditems.query.filter(or_(Relateditems.item_id == item_[0].id,
                                                               Relateditems.related_item_id == item_[0].id)).all()
                for related_item_ in related_items_:
                    db.session.delete(related_item_)
                db.session.commit()

                item_images_ = ItemImage.query.filter_by(item_id=item_[0].id).all()
                for item_image_ in item_images_:
                    if item_image_ is not None:
                        image_id = item_image_.image_id
                        image_ = Image.query.filter_by(id=image_id).first()
                        if image_ is not None:
                            db.session.delete(image_)

                            # Delete the image files
                            file_to_rem = pathlib.Path(os.path.join(app.config['UPLOAD_FOLDER'], image_.image_filename))
                            file_to_rem.unlink(missing_ok=False)

                        db.session.delete(item_image_)

                db.session.delete(item_[0])
                number_items_deleted += 1

        db.session.commit()

    return number_items_deleted


def edit_items_locations(item_ids: list, user: User, location_id: int, specific_location: str):
    with app.app_context():
        stmt = select(Item) \
            .where(Item.user_id == user.id) \
            .where(Item.id.in_(item_ids))
        results_ = db.session.execute(stmt).all()

        for item_ in results_:
            if location_id != 0:
                item_[0].location_id = location_id

            if specific_location is not None:
                item_[0].specific_location = specific_location
        db.session.commit()
        return


def copy_items(item_ids: list, user: User, inventory_id: int):
    """
        link - just add new line in ItemInventory
        move - change inventory id in ItemInventory
        copy - duplicate item, add new line in ItemInventory
    """

    with app.app_context():
        if inventory_id == -1:
            user_default_inventory = get_user_default_inventory(user_id=user.id)
            inventory_id = user_default_inventory.id

        stmt = db.session.query(Item, InventoryItem) \
            .join(InventoryItem, InventoryItem.item_id == Item.id) \
            .join(User) \
            .where(Item.user_id == user.id) \
            .where(Item.id.in_(item_ids))
        results_ = db.session.execute(stmt).all()

        for item_, inventory_item_ in results_:

            tag_arr = []
            for tag in item_.tags:
                tag_arr.append(tag.tag.replace("@#$", " "))

            new_ = add_item_to_inventory(item_name=item_.name, item_desc=item_.description,
                                         item_type=item_.item_type,
                                         item_tags=tag_arr, inventory_id=inventory_id,
                                         item_location_id=item_.location_id,
                                         item_specific_location=item_.specific_location,
                                         user_id=user.id, custom_fields=item_.fields)

        db.session.commit()

    return


def move_items(item_ids: list, user: User, inventory_id: int):
    """
        link - just add new line in ItemInventory
        move - change inventory id in ItemInventory
        copy - duplicate item, add new line in ItemInventory
    """

    with app.app_context():

        if inventory_id == -1:
            user_default_inventory = get_user_default_inventory(user_id=user.id)
            inventory_id = user_default_inventory.id

        stmt = select(Item, InventoryItem) \
            .join(InventoryItem, InventoryItem.item_id == Item.id) \
            .join(User) \
            .where(Item.user_id == user.id) \
            .where(Item.id.in_(item_ids))
        results_ = db.session.execute(stmt).all()

        for item_, inventory_item_ in results_:
            inventory_item_.inventory_id = inventory_id

        db.session.commit()

    return


def link_items(item_ids: list, user: User, inventory_id: int):
    with app.app_context():
        if inventory_id == -1:
            user_default_inventory = get_user_default_inventory(user_id=user.id)
            inventory_id = user_default_inventory.id

        stmt = db.session.query(Item, InventoryItem) \
            .join(InventoryItem, InventoryItem.item_id == Item.id) \
            .join(User) \
            .where(Item.user_id == user.id) \
            .where(Item.id.in_(item_ids))
        results_ = db.session.execute(stmt).all()

        for item_, inventory_item_ in results_:
            if inventory_item_.inventory_id != inventory_id:
                new_inventory_item_ = InventoryItem(inventory_id=inventory_id, item_id=item_.id,
                                                    access_level=inventory_item_.access_level)

                db.session.add(new_inventory_item_)

        db.session.commit()

        return


def delete_items_from_inventory(item_ids: list, inventory_id: int, user: User):
    with app.app_context():
        stmt = select(UserInventory, Inventory).join(Inventory).join(User).where(User.id == user.id).where(
            Inventory.id == inventory_id)
        user_inventory_, inventory_ = db.session.execute(stmt).first()

        number_items_deleted = 0

        for item_id in item_ids:
            item_ = find_item(item_id=item_id, user_id=user.id)
            if item_ is not None:
                inventory_.items.remove(item_)
                db.session.delete(item_)
                number_items_deleted += 1

        db.session.commit()

    return number_items_deleted


def update_item_inventory_by_invid(item_data: dict, inventory_id: int, user: User):
    with app.app_context():
        item_id = item_data['id']

        stmt = select(UserInventory, Inventory, Item).join(Inventory).join(User).where(User.id == user.id).where(
            Inventory.id == inventory_id).where(Item.id == item_id)
        r = db.session.execute(stmt).first()

        r[2].name = item_data['name']
        r[2].description = item_data['description']
        r[2].item_type = item_data['item_type']
        r[2].location_id = item_data['item_location']

        item_tags = item_data['item_tags']
        if not isinstance(item_tags, list):
            item_tags = item_tags.strip()
            item_tags = item_tags.replace(" ", "@#$")
            if "," in item_tags:
                item_tags_list = item_tags.split(",")
        else:
            item_tags_list = item_tags

        r[2].tags = []
        for tag in item_tags_list:
            instance = db.session.query(Tag).filter_by(tag=tag).one_or_none()
            if not instance:
                instance = Tag(tag=tag)

            r[2].tags.append(instance)

        db.session.commit()


def get_or_create_item(name_, description_, tags_):
    with app.app_context():
        instance = db.session.query(Item).filter_by(name=name_, description=description_).one_or_none()
        if not instance:
            instance = Item(name=name_, description=description_)
            db.session.add(instance)
            db.session.commit()

            for tag in tags_:
                t = get_or_create(Tag, tag=tag)[0]
                # db.session.add(t)
                instance.tags.append(t)
            try:
                db.session.add(instance)
                db.session.commit()

            except Exception as e:
                print(e)
                db.session.rollback()
                instance = db.session.query(Item).filter_by(name=name_, description=description_).one()
                return instance, False
            else:
                return instance, True


def get_or_create(model, defaults=None, **kwargs):
    with app.app_context():
        instance = db.session.query(model).filter_by(**kwargs).one_or_none()
        if instance:
            return instance, False
        else:
            params = {k: v for k, v in kwargs.items() if not isinstance(v, ClauseElement)}
            params.update(defaults or {})
            instance = model(**params)
            try:
                db.session.add(instance)
                db.session.commit()

            except Exception as e:
                print(e)
                db.session.rollback()
                instance = db.session.query(model).filter_by(**kwargs).one()
                return instance, False
            else:
                return instance, True


def add_item_inventory_by_invid(item: Item, inventory_id: int, user: User):
    with app.app_context():
        stmt = select(UserInventory, Inventory).join(Inventory).join(User).where(User.id == user.id).where(
            Inventory.id == inventory_id)
        r = db.session.execute(stmt).first()[1]

        r.items.append(item)
        db.session.commit()


def add_item_to_inventory2(item_name, item_desc, item_type,
                           item_tags, item_location: int,
                           inventory_id: int, user: User, item_specific_location: str = None):
    with app.app_context():

        stmt = select(Inventory).where(Inventory.id == inventory_id)
        inventory_ = db.session.execute(stmt).first()[0]

        new_item = Item(name=item_name, description=item_desc,
                        item_type=item_type, location_id=item_location,
                        specific_location=item_specific_location, user_id=user.id)

        for tag in item_tags:
            instance = db.session.query(Tag).filter_by(tag=tag).one_or_none()
            if not instance:
                instance = Tag(tag=tag)

            new_item.tags.append(instance)

        inventory_.items.append(new_item)

        db.session.flush()
        item_slug = f"{str(new_item.id)}-{slugify(item_name)}"
        new_item.slug = item_slug

        db.session.commit()


def get_user_default_item_type(user_id: int):
    with app.app_context():
        user_default_item_type = ItemType.query.filter_by(user_id=user_id, name="none").one_or_none()
        return user_default_item_type

def commit():
    db.session.commit()


def add_item_to_inventory(item_name, item_desc, item_type=None, item_tags=None, inventory_id=None, user_id=None,
                          item_location_id=None, item_specific_location="", custom_fields=None):
    app_context = app.app_context()

    with app_context:

        if custom_fields is None:
            custom_fields = {}

        if item_type is None:
            item_type = "none"

        new_item = Item(name=item_name, description=item_desc, user_id=user_id,
                        location_id=item_location_id, specific_location=item_specific_location)

        db.session.add(new_item)
        # get new item ID
        db.session.flush()
        item_slug = f"{str(new_item.id)}-{slugify(item_name)}"
        new_item.slug = item_slug

        if item_type is None:
            item_type = "None"

        if isinstance(item_type, int):
            new_item.item_type = item_type
        else:
            item_type_ = db.session.query(ItemType).filter_by(name=item_type.lower()).filter_by(
                user_id=user_id).one_or_none()

            if item_type_ is None:
                item_type_ = ItemType(name=item_type, user_id=user_id)
                db.session.add(item_type_)
                db.session.commit()
                db.session.flush()

            new_item.item_type = item_type_.id

        for tag in item_tags:
            if tag != '':
                tag = tag.strip()
                tag = tag.replace(" ", "@#$")
                instance = db.session.query(Tag).filter_by(tag=tag).one_or_none()
                if not instance:
                    instance = Tag(tag=tag, user_id=user_id)

                new_item.tags.append(instance)

        if inventory_id is None or inventory_id == '':
            default_user_inventory_ = get_user_default_inventory(user_id=user_id)
            if default_user_inventory_ is not None:
                default_user_inventory_id_ = default_user_inventory_.id
                stmt = db.session.query(Inventory).where(Inventory.id == default_user_inventory_id_)
                inventory_ = db.session.execute(stmt).first()[0]
        else:
            stmt = db.session.query(Inventory).where(Inventory.id == inventory_id)
            inventory_ = db.session.execute(stmt).first()[0]

        inventory_.items.append(new_item)

        db.session.add(new_item)

        #db.session.commit()

        add_new_item_field(new_item, custom_fields, user_id=user_id, app_context=app_context)

        return_data = {
            "item": {
                "id": new_item.id,
                "name": new_item.name,
                "description": new_item.description,
                "user_id": new_item.user_id,
            }
        }
        return_data['item']['tags'] = []
        item_tags = new_item.tags
        for tag in item_tags:
            return_data['item']['tags'].append({"tag": tag.tag})

        return return_data


def get_or_add_new_location(location_name: str, location_description: str, to_user_id: User) -> Union[dict, None]:
    with app.app_context():
        location_ = Location.query.filter_by(name=location_name).filter_by(user_id=to_user_id).one_or_none()
        if location_ is None:
            try:
                location_ = Location(name=location_name, description=location_description, user_id=to_user_id)
                db.session.add(location_)
                db.session.commit()
                db.session.flush()
                db.session.expire_all()
            except Exception as e:
                return None
        return {
            "id": location_.id,
            "name": location_.name,
            "description": location_.description
        }


def add_new_template(name: str, fields: str, to_user: User) -> Location:
    with app.app_context():
        try:
            template_ = FieldTemplate(name=name, fields=fields, user_id=to_user.id)
            db.session.add(template_)
            db.session.commit()
            db.session.flush()
            db.session.expire_all()
            return template_
        except Exception as e:
            print(e)


def get_users_for_inventory(inventory_id: int, current_user_id: int):
    with app.app_context():
        stmt = db.session.query(User, UserInventory.access_level) \
            .join(User, UserInventory.user_id == User.id) \
            .filter(UserInventory.inventory_id == inventory_id)

        result = db.session.execute(stmt).all()

        return dict(result)


def delete_user_to_inventory(inventory_id: int, user_to_delete_id: int):
    with app.app_context():
        user_inventory_ = UserInventory.query.filter(UserInventory.inventory_id == inventory_id) \
            .filter(UserInventory.user_id == user_to_delete_id).one_or_none()

        if user_inventory_ is not None:
            if user_inventory_.access_level != __OWNER__:
                db.session.delete(user_inventory_)
                db.session.commit()
                return True
            else:
                return False
        else:
            return False


def add_user_notification(to_user_id: int, from_user_id, message: str):
    with app.app_context():
        user_ = db.session.query(User).filter(User.id == to_user_id).one()
        if user_ is not None:
            from_user_ = db.session.query(User).filter(User.id == from_user_id).one()
            if from_user_ is not None:
                notification_ = Notification(text=message, from_user=from_user_)
                user_.notifications.append(notification_)
                db.session.commit()


def add_user_to_inventory(inventory_id: int, current_user_id: int, user_to_add_username: str,
                          added_user_access_level: int):
    with app.app_context():
        user_inventory_ = UserInventory.query.filter(UserInventory.inventory_id == inventory_id) \
            .filter(UserInventory.user_id == current_user_id).one_or_none()

        if user_inventory_ is not None:
            if user_inventory_.access_level == __OWNER__:
                if added_user_access_level != __OWNER__:

                    user_to_add_ = find_user_by_username(username=user_to_add_username)
                    if user_to_add_ is not None:
                        if user_to_add_ is not None:

                            # check if a user_inventory exists
                            user_to_add_inventory_ = UserInventory.query.filter(
                                UserInventory.inventory_id == inventory_id) \
                                .filter(UserInventory.user_id == user_to_add_.id).one_or_none()

                            if user_to_add_inventory_ is not None:
                                user_to_add_inventory_.access_level = added_user_access_level
                                db.session.commit()

                            else:
                                ui = UserInventory(user_id=user_to_add_.id, inventory_id=inventory_id,
                                                   access_level=added_user_access_level)
                                db.session.add(ui)
                                db.session.commit()

                            add_user_notification(from_user_id=current_user_id, to_user_id=user_to_add_.id,
                                                  message=f"You have been added to the following inventory")
                            return True

                    else:  # the username does not exist
                        return False
                else:
                    return False  # don't support owner change right now
            else:  # current user was not the inventory owner
                return False
        else:  # inventory was not found
            return False


def get_user_inventory_by_id(user_id: int, inventory_id: int) -> Inventory:
    session = db.session
    stmt = select(UserInventory).where(UserInventory.user_id == user_id) \
        .where(UserInventory.inventory_id == inventory_id)
    r = session.execute(stmt).one_or_none()

    return r


def find_item_by_slug(item_slug: str, user_id: int) -> Item:
    item_ = Item.query.filter_by(slug=item_slug).filter_by(user_id=user_id).first()
    return item_


def get_item_by_slug(item_slug: str):
    stmt = db.session.query(Item, ItemType.name, InventoryItem) \
        .join(InventoryItem, InventoryItem.item_id == Item.id) \
        .join(ItemType, ItemType.id == Item.item_type) \
        .join(Location, Location.id == Item.location_id) \
        .where(Item.slug == item_slug)

    result = db.session.execute(stmt).first()
    return result


def get_item_by_slug2(username: str, item_slug: str, user: User):
    item_user_ = find_user_by_username(username=username)

    stmt = select(Item, ItemType.name, InventoryItem) \
        .join(InventoryItem, InventoryItem.item_id == Item.id) \
        .join(ItemType, ItemType.id == Item.item_type) \
        .join(Location, Location.id == Item.location_id) \
        .where(Item.slug == item_slug)

    result = db.session.execute(stmt).first()
    if result is not None:
        item_, item_type_string, inventory_item_ = db.session.execute(stmt).first()

        if item_ is not None:
            if user is not None:
                if user.id == item_user_.id:
                    return {
                        "status": "success", "message": "", "access": "owner",
                        "item": item_, "item_type": item_type_string,
                        "inventory_item": inventory_item_
                    }
            elif inventory_item_.access_level == __PUBLIC__:
                return {
                    "status": "success", "message": "", "access": "public",
                    "item": item_, "item_type": item_type_string,
                    "inventory_item": inventory_item_
                }
            else:
                return {
                    "status": "error", "message": "no access", "access": "denied",
                    "item": None, "item_type": None,
                    "inventory_item": None
                }
    else:
        return {
            "status": "error", "message": "no item", "access": "n/a",
            "item": None, "item_type": None,
            "inventory_item": None
        }


def get_item_by_slug2(username: str, item_slug: str, user: User):
    session = db.session
    user_ = find_user_by_username(username=username)

    full_slug = f"{user.id}-{item_slug}"
    item_ = find_item_by_slug(item_slug=full_slug, user_id=user_.id)

    stmt = select(Item, Inventory, ItemType, Location) \
        .join(Inventory.items) \
        .join(InventoryItem) \
        .join(Location, Item.location_id == Location.id) \
        .join(UserInventory) \
        .join(ItemType) \
        .where(UserInventory.user_id == user_.id) \
        .where(Item.id == item_.id)
    r = session.execute(stmt).first()

    return r


def get_item(username: str, inventory_slug: str, item_slug: str):
    session = db.session
    user_ = find_user_by_username(username=username)

    inventory_, user_inventory_ = find_inventory_by_slug(inventory_slug=inventory_slug, user_id=user_.id)

    item_ = find_item_by_slug(item_slug=item_slug, user_id=user_.id)

    stmt = select(Item, ItemType) \
        .join(Inventory.items) \
        .join(InventoryItem) \
        .join(UserInventory) \
        .join(ItemType) \
        .where(InventoryItem.inventory_id == inventory_.id) \
        .where(UserInventory.user_id == user_.id) \
        .where(Item.id == item_.id)
    r = session.execute(stmt).first()

    return r


def get_items_for_inventory(user: User, inventory_id: int):
    session = db.session
    stmt = select(Item, ItemType, Location) \
        .join(Inventory.items) \
        .join(InventoryItem) \
        .join(UserInventory) \
        .join(Location, Item.location_id == Location.id) \
        .join(ItemType) \
        .where(InventoryItem.inventory_id == inventory_id)  # .where(UserInventory.user_id == user.id)
    items_ = session.execute(stmt).all()

    return items_


def delete_item_from_inventory(user: User, inventory_id: int, item_id: int) -> None:
    stmt = select(UserInventory, Item).join(Inventory).join(User).filter(
        and_(User.id == user.id, Inventory.id == inventory_id, Item.id == item_id))

    item = db.session.execute(stmt).first()
    if item is not None:
        item = item[1]
        db.session.delete(item)
        db.session.commit()


def edit_inventory_data(user_id: int, inventory_id: int, name: str,
                        description: str, public: int, access_level: int) -> None:
    session = db.session

    stmt = select(UserInventory, Inventory).join(Inventory) \
        .where(UserInventory.user_id == user_id) \
        .where(UserInventory.inventory_id == inventory_id)

    r = session.execute(stmt)

    ff = r.one_or_none()

    if ff is not None:
        ff[1].name = name
        ff[1].description = description
        ff[1].public = public
        ff[0].access_level = access_level
        db.session.commit()


def delete_templates_from_db(user_id: str, template_ids) -> None:
    if not isinstance(template_ids, list):
        template_ids = [template_ids]

    stmt = select(FieldTemplate).join(User) \
        .where(FieldTemplate.user_id == user_id) \
        .where(FieldTemplate.id.in_(template_ids))
    templates_ = db.session.execute(stmt).all()

    # get all the niventories that use this template

    for template_ in templates_:
        template_ = template_[0]

        inventories_ = Inventory.query.filter(Inventory.field_template == template_.id).all()
        for inventory_ in inventories_:
            inventory_.field_template = None

        db.session.commit()

        db.session.delete(template_)
        db.session.commit()


def delete_location(user_id: int, location_ids) -> dict:
    if not isinstance(location_ids, list):
        location_ids = [location_ids]

    stmt = select(Location).join(User) \
        .where(Location.user_id == user_id) \
        .where(Location.id.in_(location_ids))
    locations_ = db.session.execute(stmt).all()

    number_items_deleted = 0
    user_default_location_ = Location.query.filter_by(name="None") \
        .filter_by(user_id=user_id).one_or_none()

    for location_ in locations_:
        if location_[0] is not None:
            location_ = location_[0]

            if location_ is not None:
                location_id = location_.id
                try:
                    # find any items with this location and chnge to None
                    if user_default_location_ is not None:
                        items_ = Item.query.filter_by(location_id=location_id)\
                            .filter_by(user_id=user_id).all()
                        for row in items_:
                            row.location_id = user_default_location_.id
                        db.session.commit()

                    db.session.delete(location_)
                    db.session.commit()

                except SQLAlchemyError as err:
                    return {"success": False}
    return {"success": True}


def get_user_inventories(current_user_id: int, requesting_user_id: int, access_level: int = -1):
    with app.app_context():

        # stmt = db.session.query(Inventory, UserInventory).join(UserInventory).filter(UserInventory.user_id==1).all()
        stmt = db.session.query(Inventory, UserInventory).join(UserInventory)

        if current_user_id is not None and requesting_user_id is not None:
            is_current_user = (current_user_id == requesting_user_id)
        else:
            if requesting_user_id is None:
                return []
            is_current_user = False

        if is_current_user:
            if access_level == -1:
                stmt = stmt.filter(UserInventory.user_id == current_user_id)
            else:
                stmt = stmt.filter(UserInventory.user_id == current_user_id) \
                    .filter(UserInventory.access_level == access_level)
        else:
            stmt = stmt.filter(UserInventory.user_id == requesting_user_id).filter(UserInventory.access_level != 0)

        r = db.session.execute(stmt).all()

        ret_results = []

        for inv, user_inv in r:
            d = {
                "inventory_id": inv.id,
                "inventory_name": inv.name,
                "inventory_description": inv.description,
                "inventory_slug": inv.slug,
                "inventory_public": inv.public,
                "inventory_owner": inv.owner.username,
                "inventory_item_count": len(inv.items),
                "inventory_access_level": user_inv.access_level
            }
            ret_results.append(d)

        return ret_results


def get_user_templates(user: User):
    session = db.session
    stmt = select(FieldTemplate).join(User).where(User.id == user.id)
    r = session.execute(stmt).all()
    return r


def get_user_template_by_id(template_id: int, user_id: int):
    session = db.session
    stmt = select(FieldTemplate).join(User).where(FieldTemplate.id == template_id)\
        .where(FieldTemplate.user_id == user_id)
    r = session.execute(stmt).one_or_none()
    return r


def get_template_fields_by_id(template_id: int):
    session = db.session
    stmt = select(TemplateField, Field) \
        .join(FieldTemplate) \
        .join(Field)\
        .where(FieldTemplate.id == template_id)
    r = session.execute(stmt).all()
    return r


def set_template_fields_orders(field_data, template_id: int, user_id: int):
    session = db.session

    user_template_ = get_user_template_by_id(template_id=template_id, user_id=user_id)
    if user_template_ is not None:

        for field_order, field_dict in field_data.items():
            field_id = field_dict[1]

            stmt = select(TemplateField).where(FieldTemplate.id == template_id)\
                .join(FieldTemplate)\
                .where(TemplateField.field_id == field_id)
            r = session.execute(stmt).one_or_none()

            if r is not None:
                r = r[0]
                r.order = field_order

        db.session.commit()

        return


def save_inventory_fieldtemplate(inventory_id, inventory_template, user_id: int):
    with app.app_context():
        inventory_, user_inventory_ = find_inventory_by_id(inventory_id=inventory_id, user_id=user_id)

        if user_inventory_.access_level == 0:
            inventory_.field_template = inventory_template

        db.session.commit()

    return


def get_user_locations(user_id: int) -> List[dict]:
    session = db.session
    stmt = select(Location).where(Location.user_id == user_id)
    r = session.execute(stmt).all()
    locations_results = []
    for row in r:
        locations_results.append(
            {
                "id": row[0].id,
                "name": row[0].name,
                "description": row[0].description,
                "user_id": row[0].user_id
            }
        )
    return locations_results


def get_number_user_locations(user_id: int):
    session = db.session
    stmt = session.query(func.count(Location.id)).where(Location.user_id == user_id)
    r = session.execute(stmt).all()
    return r[0][0]


def get_user_location_by_id(location_id: str, user_id: int):
    session = db.session
    stmt = select(Location).join(User).where(User.id == user_id).where(Location.id == location_id)
    r = session.execute(stmt).one_or_none()
    if r is not None:
        return r[0].__dict__
    return None


def get_item_fields(item_id: int):
    with app.app_context():
        # stmt = select(Field.field, ItemField).join(Item).join(Field, ItemField.field_id == Field.id) \
        #     .filter(ItemField.item_id == item_id) \
        #     .filter(ItemField.show == True)
        # ddd = db.session.execute(stmt).all()

        stmt = select(Field, ItemField, TemplateField) \
            .join(Field, ItemField.field_id == Field.id) \
            .join(TemplateField, TemplateField.field_id == Field.id) \
            .filter(ItemField.item_id == item_id) \
            .filter(ItemField.show == True)
        ddd = db.session.execute(stmt).all()

        return ddd


def get_all_item_fields(item_id: int):
    with app.app_context():
        stmt = select(Field.field, ItemField).join(Item).join(Field, ItemField.field_id == Field.id) \
            .filter(ItemField.item_id == item_id)
        ddd = db.session.execute(stmt).all()
        return ddd


def get_all_fields():
    with app.app_context():
        stmt = select(Field.field, Field)
        ddd = db.session.execute(stmt).all()
        return ddd


def set_inventory_default_fields(inventory_id, user, default_fields):
    with app.app_context():
        if inventory_id == '':
            inventory_ = get_user_default_inventory(user_id=user.id)
        else:
            inventory_ = Inventory.query.filter_by(id=inventory_id).first()

        user_inventory_ = UserInventory.query \
            .filter_by(inventory_id=inventory_.id).filter_by(user_id=user.id).first()
        inventory_.default_fields = ",".join(default_fields)

        db.session.commit()
        return


def save_template_fields(template_name, fields, user):
    with app.app_context():

        field_template_ = FieldTemplate.query.filter_by(name=template_name).filter_by(user_id=user.id).one_or_none()

        if field_template_ is None:

            field_template_ = FieldTemplate(name=template_name, user_id=user.id)
            db.session.add(field_template_)

            for field in fields:
                field_ = Field.query.filter_by(id=field).one_or_none()
                if field_ is not None:
                    field_template_.fields.append(field_)

        else:
            field_template_.name = template_name

            field_template_.fields = []
            for field in fields:
                field_ = Field.query.filter_by(id=field).one_or_none()
                if field_ is not None:
                    field_template_.fields.append(field_)

        db.session.commit()

        # now do the sorting
        stmt = select(TemplateField).where(FieldTemplate.id == field_template_.id)
        r = db.session.execute(stmt).all()

        max_order = db.session.query(func.max(TemplateField.order)).scalar()

        for row in r:
            if row[0].order == 0:
                max_order += 1
                row[0].order = max_order

        db.session.commit()

        return


def update_item_fields(data, item_id: int):
    with app.app_context():
        stmt2 = select(Field.id, ItemField) \
            .join(Item) \
            .join(Field) \
            .filter(ItemField.item_id == item_id) \
            .filter(ItemField.field_id.in_(list(data.keys())))

        ddd2 = db.session.execute(stmt2).all()

        for k, v in dict(ddd2).items():
            v.value = data[k]

        db.session.commit()


def add_new_item_field(item, custom_fields, user_id, app_context=None):
    if app_context is None:
        app_context = app.app_context()

    with app_context:

        for field_name, field_value in custom_fields.items():

            field_ = Field.query.filter_by(field=field_name).one_or_none()
            if field_ is None:
                field_slug = slugify(field_name)
                field_ = Field(field=field_name, slug=field_slug)
                db.session.add(field_)
                db.session.flush()

            field_id = field_.id
            field_.items.append(item)

            db.session.commit()

            item_field_ = ItemField.query.filter_by(field_id=field_id).filter_by(item_id=item.id).one_or_none()
            item_field_.value = field_value
            item_field_.show = True
            item_field_.user_id=user_id

            db.session.commit()


def set_field_status(item_id, field_ids, is_visible=True):
    with app.app_context():

        all_fields = get_all_fields()

        for field_name, field in dict(all_fields).items():
            show = (field.id in field_ids)

            instance_ = ItemField.query.filter_by(item_id=int(item_id), field_id=int(field.id)).first()
            if instance_:
                instance_.show = show
                db.session.commit()
            else:
                instance_ = ItemField(item_id=int(item_id), field_id=int(field.id), show=show)
                db.session.add(instance_)

            db.session.commit()
