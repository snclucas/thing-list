import datetime

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

from app import db
from search import query_index, add_to_index, remove_from_index


class SearchableMixin(object):
    @classmethod
    def search(cls, expression, page, per_page):
        ids, total = query_index(cls.__tablename__, expression, page, per_page)
        if total == 0:
            return cls.query.filter_by(id=0), 0
        when = []
        for i in range(len(ids)):
            when.append((ids[i], i))
        return cls.query.filter(cls.id.in_(ids)).order_by(
            db.case(when, value=cls.id)), total

    @classmethod
    def before_commit(cls, session):
        session._changes = {
            'add': list(session.new),
            'update': list(session.dirty),
            'delete': list(session.deleted)
        }

    @classmethod
    def after_commit(cls, session):
        for obj in session._changes['add']:
            if isinstance(obj, Tag):
                add_to_index(obj.__tablename__, obj.__dict__)
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['update']:
            # if isinstance(obj, Item):
            #
            #     dict_tags = []
            #     tags = obj.tags
            #     for tag in tags:
            #
            #         dict_tags.append({'tag': tag.tag, 'id': tag.id})
            #     obj.tags = dict_tags
            #
            #     add_to_index(obj.__tablename__, obj)



            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['delete']:
            if isinstance(obj, SearchableMixin):
                remove_from_index(obj.__tablename__, obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        for obj in cls.query:
            add_to_index(cls.__tablename__, obj)


#db.event.listen(db.session, 'before_commit', SearchableMixin.before_commit)
#db.event.listen(db.session, 'after_commit', SearchableMixin.after_commit)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), nullable=True, unique=True)
    password = db.Column(db.String(255), nullable=False, server_default='')
    email = db.Column(db.String(255), nullable=False, unique=True)
    is_active = db.Column(db.Boolean(), default=True)
    is_admin = db.Column(db.Boolean(), default=False)
    user_created = db.Column(db.DateTime(), default=datetime.datetime.now())
    email_confirmed_at = db.Column(db.DateTime(), default=None)
    inventories = db.relationship('Inventory', secondary='inventory_users',
                                  back_populates='users', cascade="all,delete", lazy='subquery')

    notifications = db.relationship('Notification', backref='users')


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.DateTime(), default=datetime.datetime.now())
    text = db.Column(db.String(50), nullable=True, unique=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True, nullable=False)
    from_user = db.relationship(User, viewonly=True, load_on_pending=True, lazy='subquery')


class FieldTemplate(db.Model):
    __tablename__ = "field_templates"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50))
    # fields = db.Column(db.String(1000), default="-1")
    fields = db.relationship('Field', secondary='fieldtemplate_fields',
                             back_populates='field_templates', lazy='subquery')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))


class TemplateField(db.Model):
    __tablename__ = "fieldtemplate_fields"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    field_id = db.Column(db.Integer, db.ForeignKey('fields.id', ondelete='CASCADE'))
    template_id = db.Column(db.Integer, db.ForeignKey('field_templates.id', ondelete='CASCADE'))


class Field(db.Model):
    __tablename__ = "fields"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    field = db.Column(db.String(255), nullable=True, unique=False)
    slug = db.Column(db.String(2000), nullable=True, unique=False)
    type = db.Column(db.String(255), nullable=True, unique=False)
    data = db.Column(db.String(255), nullable=True, unique=False)
    items = db.relationship('Item', secondary='item_fields', back_populates='fields', cascade="all,delete")
    field_templates = db.relationship('FieldTemplate', secondary='fieldtemplate_fields', back_populates='fields')


class Location(db.Model):
    __tablename__ = "locations"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=True, unique=False)
    description = db.Column(db.String(50), nullable=True, unique=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))


class Inventory(db.Model):
    __tablename__ = "inventories"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50))
    slug = db.Column(db.String(50), nullable=True, unique=False)
    description = db.Column(db.String(255))
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True, nullable=False)
    owner = db.relationship(User, load_on_pending=True, lazy='subquery')
    users = db.relationship('User', secondary='inventory_users', back_populates='inventories', lazy='subquery')
    items = db.relationship('Item', secondary='inventory_items', back_populates='inventories', lazy='subquery')
    default_fields = db.Column(db.String(1000), default="-1")
    field_template = db.Column(db.Integer, db.ForeignKey('field_templates.id'), nullable=True)
    public = db.Column(db.Boolean(), nullable=True, unique=False, default=False)


class Item(db.Model):
    __tablename__ = "items"
    __searchable__ = ['name', 'description']

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    item_type = db.Column(db.Integer, db.ForeignKey('item_type.id'), nullable=True)
    name = db.Column(db.String(255), nullable=False, unique=False)
    slug = db.Column(db.String(255), nullable=True, unique=False)
    description = db.Column(db.String(2000), nullable=True, unique=False)
    inventories = db.relationship('Inventory', secondary='inventory_items', back_populates='items', lazy='subquery')
    tags = db.relationship('Tag', secondary='item_tags', back_populates='items', lazy='subquery')
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), primary_key=True, default=1)
    specific_location = db.Column(db.String(50), nullable=True, unique=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    images = db.relationship('Image', secondary='item_images', back_populates='items', lazy='subquery')
    main_image = db.Column(db.String(255), nullable=True, unique=False)
    fields = db.relationship('Field', secondary='item_fields', back_populates='items', lazy='subquery')


class ItemField(db.Model):
    __tablename__ = "item_fields"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    field_id = db.Column(db.Integer, db.ForeignKey('fields.id', ondelete='CASCADE'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'))
    value = db.Column(db.String(255), nullable=True, unique=False)
    show = db.Column(db.Boolean(), nullable=True, unique=False, default=False)
    user_id = db.Column(db.Integer, nullable=True, unique=False, default=-1)
    __table_args__ = (UniqueConstraint('field_id', 'item_id', name='_item_field_uc'),
                      )


class Image(db.Model):
    __tablename__ = "images"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    image_filename = db.Column(db.String(255), nullable=True, unique=False)
    items = db.relationship('Item', secondary='item_images', back_populates='images',
                            cascade="all,delete", lazy='subquery')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)


class ItemImage(db.Model):
    __tablename__ = "item_images"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id', ondelete='CASCADE'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'))


class UserInventory(db.Model):
    __tablename__ = "inventory_users"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'))
    access_level = db.Column(db.Integer, default=0)


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    access_level = db.Column(db.Integer, default=0)


class ItemType(db.Model):
    __tablename__ = "item_type"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=True, unique=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    __table_args__ = (UniqueConstraint('name', 'user_id', name='_name_userid_uc'),)


class Tag(db.Model):
    __tablename__ = "tags"
    __searchable__ = ['tag']
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tag = db.Column(db.String(50), nullable=True, unique=True)
    items = db.relationship('Item', secondary='item_tags', back_populates='tags', cascade="all,delete")
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)


class ItemTag(db.Model):
    __tablename__ = "item_tags"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'))
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'))


class UserLocation(db.Model):
    __tablename__ = "user_location"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id', ondelete='CASCADE'))
