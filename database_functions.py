import os
import pathlib

from typing import Optional

import flask_bcrypt

from slugify import slugify
from sqlalchemy import select, and_, ClauseElement
from sqlalchemy.exc import SQLAlchemyError

from app import db, app
from models import Inventory, User, Item, UserInventory, InventoryItem, ItemType, Tag, \
    Location, Image, ItemImage, Field, ItemField, FieldTemplate

_NONE_ = "None"

__PUBLIC__ = 2
__PRIVATE__ = 0


def drop_then_create():
    db.drop_all()
    db.create_all()
    db.session.commit()


def post_user_add_hook(new_user: User):
    with app.app_context():
        add_user_inventory(name=f"__default__{new_user.username}", description=f"Default inventory",
                           user_id=new_user.id)
        add_new_location(location_name=_NONE_, location_description="No location", to_user=new_user)
        add_new_user_itemtype(name=_NONE_, user_id=new_user.id)
    # add default locations, types


def add_new_inventory(name: str, description: str, user: User):
    return add_user_inventory(name=name, description=description, user_id=user.id)


def get_user_default_inventory(user: User):
    with app.app_context():
        # Find user default inventory
        user_default_inventory_ = Inventory.query.filter_by(name=f"__default__{user.username}").filter_by().first()
        return user_default_inventory_


def delete_inventory(inventory_id: int, user: User):
    """
    If the User has Items within the Inventory - re-link Items to Users default Inventory via the ItemInventory table
    Delete the UserInventory for the user
    If there are no more UserInventory links to the Inventory - delete the Inventory
    """

    with app.app_context():
        user_inventory_ = UserInventory.query.filter_by(user_id=user.id).filter_by(inventory_id=inventory_id).first()

        if user_inventory_ is not None:
            # Find out if any other users point to this inventory, if not delete it
            inventory_id_to_delete = user_inventory_.inventory_id

            user_default_inventory_ = get_user_default_inventory(user=user)

            inv_items_ = InventoryItem.query.filter_by(inventory_id=inventory_id_to_delete).all()
            for row in inv_items_:
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

            d = db.session.query(Item, ItemType.name, Location.name,
                                 InventoryItem.access_level) \
                .join(InventoryItem, InventoryItem.item_id == Item.id) \
                .join(Inventory, Inventory.id == InventoryItem.inventory_id) \
                .join(ItemType, ItemType.id == Item.item_type) \
                .join(Location, Location.id == Item.location_id)

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

            if item_type is not None:
                d = d.filter(Item.item_type == item_type)

            if item_location is not None:
                d = d.filter(Location.id == item_location)

            if item_specific_location is not None:
                d = d.filter(Item.specific_location == item_specific_location)

            if item_tags is not None and item_tags != "":
                item_tags = item_tags.split(",")

                for tag_ in item_tags:
                    tag_ = tag_.strip()
                    tag_ = tag_.replace(" ", "@#$")
                    t_ = find_tag(tag=tag_)

                    if t_ is not None:
                        d = d.filter(Item.tags.contains(t_))

        if inventory_id is not None:
            d = d.filter(InventoryItem.inventory_id == inventory_id)

        sd = d.all()

        return sd


def change_item_access_level(item_id: int, access_level: int, user_id: int):
    with app.app_context():
        d = db.session.query(Item, InventoryItem) \
            .join(InventoryItem, InventoryItem.item_id == Item.id) \
            .join(Inventory, Inventory.id == InventoryItem.inventory_id) \
            .join(UserInventory, UserInventory.user_id == Item.user_id) \
            .filter(Item.id == item_id) \
            .filter(Item.user_id == user_id)

        item_, inventory_item_ = d.first()
        if item_ is not None:
            inventory_item_.access_level = access_level

        db.session.commit()


def add_user(username: str, email: str, password: str) -> User:
    with app.app_context():
        password_hash = flask_bcrypt.generate_password_hash(password)
        user = User(username=username, email=email, password=password_hash)
        db.session.add(user)
        db.session.commit()
        post_user_add_hook(new_user=user)
        return user


def get_all_user_locations(user: User) -> list[Location]:
    user_locations_ = Location.query.filter_by(user_id=user.id).all()
    return user_locations_


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


def add_new_user_itemtype(name: str, user_id):
    item_type_ = find_type_by_text(type_text=name.lower(), user_id=user_id)
    print(f"Seraching for type {name.lower()} - result {item_type_}")
    if item_type_ is None:
        with app.app_context():
            new_item_type_ = ItemType(name=name.lower(), user_id=user_id)
            db.session.add(new_item_type_)
            db.session.commit()


def find_user(username_or_email: str) -> User:
    user = User.query.filter_by(username=username_or_email).first()
    if not user:
        user = User.query.filter_by(email=username_or_email).first()
    return user


def find_type_by_text(type_text: str, user_id: int = None) -> ItemType:
    if user_id is None:
        item_type_ = ItemType.query.filter_by(name=type_text.lower()).first()
    else:
        item_type_ = ItemType.query.filter_by(name=type_text.lower()).filter_by(user_id=user_id).first()
    return item_type_


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


def find_item(item_id: int, user_id: int = None) -> Item:
    if user_id is None:
        item_ = Item.query.filter_by(id=item_id).first()
    else:
        item_ = Item.query.filter_by(id=item_id).filter_by(user_id=user_id).first()
    return item_


def find_tag(tag: str) -> User:
    tag_ = Tag.query.filter_by(tag=tag).first()
    return tag_


def find_location(location_id: int) -> Location:
    location_ = Location.query.filter_by(id=location_id).first()
    return location_


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

    else:  # get the inventory if it is public
        stmt = select(UserInventory, Inventory) \
            .join(UserInventory) \
            .join(User) \
            .where(UserInventory.access_level == __PUBLIC__) \
            .where(Inventory.slug == inventory_slug)

    res = db.session.execute(stmt).first()
    if res is not None:
        user_inventory_, inventory_ = res[0], res[1]

        return inventory_, user_inventory_

    else:
        return None, None


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
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], image_.image_filename))
                except OSError:
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
        r[0].description = item_data['description']
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
                instance = Tag(tag=tag)

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

        result = get_item_by_slug(username=user.username, item_slug=r[0].slug, user=user)
        return result


def delete_items(item_ids: list, user: User):
    with app.app_context():
        stmt = select(Item).join(User) \
            .where(Item.user_id == user.id) \
            .where(Item.id.in_(item_ids))
        items_ = db.session.execute(stmt).all()

        number_items_deleted = 0

        for item_ in items_:
            if item_[0] is not None:

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


def move_items(item_ids: list, user: User, inventory_id: int):
    with app.app_context():

        if inventory_id == -1:
            user_default_inventory = get_user_default_inventory(user=user)
            inventory_id = user_default_inventory.id

        stmt = select(Item, InventoryItem) \
            .join(InventoryItem, InventoryItem.item_id == Item.id) \
            .join(User) \
            .where(Item.user_id == user.id) \
            .where(Item.id.in_(item_ids))
        items_ = db.session.execute(stmt).all()

        for item_, iventory_item_ in items_:
            iventory_item_.inventory_id = inventory_id

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


def add_item_to_inventory(item_name, item_desc, item_type=None, item_tags=None, inventory_id=None, user_id=None,
                          item_location=1, item_specific_location="", custom_fields=None):
    app_context = app.app_context()

    with app_context:

        new_item = Item(name=item_name, description=item_desc, user_id=user_id,
                        location_id=item_location, specific_location=item_specific_location)

        db.session.add(new_item)
        # get new item ID
        db.session.flush()
        item_slug = f"{str(new_item.id)}-{slugify(item_name)}"
        new_item.slug = item_slug

        if item_type is None:
            item_type = "None"

        item_type_ = db.session.query(ItemType).filter_by(name=item_type.lower()).filter_by(user_id=user_id).one_or_none()

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
                    instance = Tag(tag=tag)

                new_item.tags.append(instance)

        if inventory_id is not None and inventory_id != '':
            stmt = db.session.query(Inventory).where(Inventory.id == inventory_id)
            inventory_ = db.session.execute(stmt).first()[0]
            inventory_.items.append(new_item)
        else:
            db.session.add(new_item)

        db.session.commit()

        add_new_item_field(new_item, custom_fields, app_context)


def add_user_inventory(name, description, user_id: int):
    ret = {}
    slug = slugify(name)

    with app.app_context():
        try:
            # add it initially private
            new_inventory = Inventory(name=name, description=description, slug=slug)
            to_user = User.query.filter_by(id=user_id).first()
            if to_user is not None:
                db.session.expire_on_commit = False
                db.session.add(new_inventory)
                db.session.flush()
                ret["id"] = new_inventory.id
                to_user.inventories.append(new_inventory)
                db.session.commit()
                db.session.expunge_all()
                return ret, "success"

        except SQLAlchemyError:
            return None, "Could not add inventory"




def add_inventory(inventory_name: str, inventory_description: str, to_user: User) -> Inventory:
    with app.app_context():
        try:
            inv = Inventory(name=inventory_name, description=inventory_description)
            to_user.inventories.append(inv)
            db.session.commit()
            db.session.flush()
            db.session.expire_all()
            return inv
        except Exception as e:
            print(e)


def add_new_location(location_name: str, location_description: str, to_user: User) -> Location:
    with app.app_context():
        try:
            location_ = Location(name=location_name, description=location_description, user_id=to_user.id)
            db.session.add(location_)
            db.session.commit()
            db.session.flush()
            db.session.expire_all()
            return location_
        except Exception as e:
            print(e)


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


def add_user_to_inventory(inventory: Inventory, user: User, access_level: int) -> UserInventory:
    ui = UserInventory(user_id=user.id, inventory_id=inventory.id, access_level=access_level)
    db.session.add(ui)
    db.session.commit()
    return ui


def get_user_inventory_by_id(user: User, inventory_id: int) -> Inventory:
    session = db.session
    stmt = select(UserInventory, Inventory).join(Inventory).join(User).where(User.id == user.id).where(
        Inventory.id == inventory_id)
    r = session.execute(stmt).first()

    return r


def find_item_by_slug(item_slug: str, user_id: int) -> Item:
    item_ = Item.query.filter_by(slug=item_slug).filter_by(user_id=user_id).first()
    return item_


def get_item_by_slug(username: str, item_slug: str, user: User):
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
            elif inventory_item_.access_level == 2:
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


def edit_inventory_data(user: User, inventory_id: int, name: str,
                        description: str, access_level: int) -> None:
    session = db.session

    stmt = select(UserInventory, Inventory, User).join(Inventory).join(User).where(User.id == user.id) \
        .where(UserInventory.inventory_id == inventory_id)

    r = session.execute(stmt)

    ff = r.first()

    if ff is not None:
        ff[1].name = name
        ff[1].description = description
        ff[0].access_level = access_level
        db.session.commit()


def delete_template_from_db(user: User, template_id: int) -> None:
    template_ = FieldTemplate.query.filter_by(id=template_id).filter_by(user_id=user.id).first()

    if template_ is not None:
        db.session.delete(template_)
        db.session.commit()


def delete_location_from_db(user: User, location_id: int) -> None:
    location_ = Location.query.filter_by(id=location_id).filter_by(user_id=user.id).first()

    if location_ is not None:
        db.session.delete(location_)
        db.session.commit()


def get_user_inventories(logged_in_user: User, requested_username: Optional[str], access_level: int = -1):
    with app.app_context():

        # stmt = select(UserInventory) #.join(Inventory, Inventory.id == UserInventory.inventory_id)

        stmt = db.session.query(UserInventory, Inventory, User)\
            .join(Inventory, Inventory.id == UserInventory.inventory_id).join(User)

        if logged_in_user is not None:

            if logged_in_user.username == requested_username or requested_username is None:
                stmt = stmt.filter(UserInventory.user_id == logged_in_user.id)
                if access_level != -1:
                    stmt = stmt.filter(access_level=access_level)
            else:
                if requested_username is not None:
                    user_ = find_user(username_or_email=requested_username)
                    if user_ is not None:
                        stmt = stmt.filter(User.id == user_.id).filter(UserInventory.access_level != 0)

        else:
            if requested_username is not None:
                user_ = find_user(username_or_email=requested_username)
                if user_ is not None:
                    stmt = stmt.filter(User.id == user_.id).filter(UserInventory.access_level == 2)

        r = db.session.execute(stmt).all()

        return r


def get_user_templates(user: User):
    session = db.session
    stmt = select(FieldTemplate).join(User).where(User.id == user.id)
    r = session.execute(stmt).all()

    return r


def save_inventory_fieldtemplate(inventory_id, inventory_template, user_id: int):
    with app.app_context():
        inventory_, user_inventory_ = find_inventory_by_id(inventory_id=inventory_id, user_id=user_id)

        if user_inventory_.access_level == 0:
            inventory_.field_template = inventory_template

        db.session.commit()

    return




def get_user_locations(user: User):
    session = db.session
    stmt = select(Location).join(User).where(User.id == user.id)
    r = session.execute(stmt).all()
    return r


def get_user_location(user: User, location_id: str):
    session = db.session
    stmt = select(Location).join(User).where(User.id == user.id).where(Location.id == location_id)
    r = session.execute(stmt).first()
    return r


def get_item_fields(item_id: int):
    with app.app_context():
        stmt = select(Field.field, ItemField).join(Item).join(Field, ItemField.field_id == Field.id) \
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
            inventory_ = get_user_default_inventory(user=user)
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

            new_field_template_ = FieldTemplate(name=template_name, user_id=user.id)
            db.session.add(new_field_template_)

            for field in fields:
                field_ = Field.query.filter_by(id=field).one_or_none()
                if field_ is not None:
                    new_field_template_.fields.append(field_)

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


def add_new_item_field(item, custom_fields, app_context=None):
    if app_context is None:
        app_context = app.app_context()

    with app_context:

        for field_name, field_value in custom_fields.items():

            field_ = Field.query.filter_by(field=field_name).one_or_none()
            if field_ is None:
                field_ = Field(field=field_name, description=field_name)
                db.session.add(field_)
                db.session.flush()

            field_id = field_.id
            field_.items.append(item)

            db.session.commit()

            item_field_ = ItemField.query.filter_by(field_id=field_id).filter_by(item_id=item.id).one_or_none()
            item_field_.value = field_value
            item_field_.show = True

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