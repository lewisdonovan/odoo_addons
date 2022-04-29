# -*- coding: utf-8 -*-
# Copyright 2022 IZI PT Solusi Usaha Mudah
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class IZIDataSourceDBOdoo(models.Model):
    _inherit = 'izi.data.source'

    type = fields.Selection(
        selection_add=[
            ('db_odoo', 'Database Odoo'),
        ])
    
    @api.model
    def create_source_db_odoo(self):
        if not self.search([('type', '=', 'db_odoo')], limit=1):
            data_source = self.create({
                'name': 'Odoo',
                'type': 'db_odoo'
            })
            data_source.get_source_tables()
        return True

    def get_cursor_db_odoo(self):
        return self.env.cr

    def close_cursor_db_odoo(self, cursor):
        pass

    def get_schema_db_odoo(self):
        return 'public'

    def dictfetchall_db_odoo(self, cursor):
        return cursor.dictfetchall()

    def authenticate_db_odoo(self):
        self.ensure_one()
        self.state = 'ready'

    def get_foreignkey_field_db_odoo(self):
        self.ensure_one()

        cursor = self.get_cursor_db_odoo()
        schema_name = self.get_schema_db_odoo()

        # Get Foreign Key Field
        cursor.execute('''
            SELECT
                kcu.table_schema,
                kcu.constraint_name,
                kcu.table_name,
                kcu.column_name,
                ccu.table_schema foreign_table_schema,
                ccu.table_name foreign_table_name,
                ccu.column_name foreign_column_name
            FROM
                information_schema.key_column_usage kcu
            JOIN information_schema.table_constraints tc ON
                (kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema)
            JOIN information_schema.constraint_column_usage ccu ON
                (kcu.constraint_name = ccu.constraint_name AND kcu.table_schema = ccu.table_schema)
            WHERE
                tc.constraint_type = 'FOREIGN KEY'
                AND kcu.table_schema = '{schema_name}'
                AND ccu.table_schema = '{schema_name}'
        '''.format(schema_name=schema_name))
        fkey_records = self.dictfetchall_db_odoo(cursor)
        fkey_by_table_column = {}
        for fkey in fkey_records:
            fkey_by_table_column['%s,%s' % (fkey.get('table_name'), fkey.get('column_name'))] = fkey

        return fkey_by_table_column

    def get_source_tables_db_odoo(self, **kwargs):
        self.ensure_one()

        cursor = self.get_cursor_db_odoo()
        schema_name = self.get_schema_db_odoo()

        Table = self.env['izi.table']
        Field = self.env['izi.table.field']

        table_by_name = kwargs.get('table_by_name')
        field_by_name = kwargs.get('field_by_name')
        fkey_by_table_column = self.get_foreignkey_field_db_odoo()

        # Get mapping oid and field type FROM pg_type
        typ_by_oid = {}
        cursor.execute("SELECT oid, typname FROM pg_type")
        dict_typs = self.dictfetchall_db_odoo(cursor)
        for typ in dict_typs:
            typ_by_oid[typ.get('oid')] = typ.get('typname')

        # Get Tables
        cursor.execute("SELECT * FROM information_schema.tables WHERE table_schema = '%s' %s" %
                       (schema_name, kwargs.get('table_filter_query')))
        table_records = self.dictfetchall_db_odoo(cursor)
        for table_record in table_records:
            table_name = table_record.get('table_name')
            table_desc = table_record.get('table_name').replace('_', ' ').title()

            # Create or Get Tables
            table = table_by_name.get(table_name)
            if table_name not in table_by_name:
                table = Table.create({
                    'active': False,
                    'name': table_desc,
                    'table_name': table_name,
                    'source_id': self.id,
                })
                field_by_name[table_name] = {}
            else:
                table_by_name.pop(table_name)

            cursor.execute("SELECT * FROM %s LIMIT 1" % table_name)
            # Get and loop column description with env.cr.description from query given above
            for desc in cursor.description:
                field_name = desc.name
                field_title = field_name.replace('_', ' ').title()
                field_type_origin = typ_by_oid.get(desc.type_code)
                field_type = Field.get_field_type_mapping(field_type_origin, self.type)
                foreign_table = None
                foreign_column = None
                if fkey_by_table_column.get('%s,%s' % (table_name, field_name)) is not None:
                    fkey = fkey_by_table_column.get('%s,%s' % (table_name, field_name))
                    field_type = 'foreignkey'
                    foreign_table = fkey.get('foreign_table_name')
                    foreign_column = fkey.get('foreign_column_name')

                # Check to create or update field
                if field_name not in field_by_name[table_name]:
                    field = Field.create({
                        'name': field_title,
                        'field_name': field_name,
                        'field_type': field_type,
                        'field_type_origin': field_type_origin,
                        'table_id': table.id,
                        'foreign_table': foreign_table,
                        'foreign_column': foreign_column,
                    })
                else:
                    field = field_by_name[table_name][field_name]
                    if field.name != field_title or field.field_type_origin != field_type_origin or \
                            field.field_type != field_type:
                        field.name = field_title
                        field.field_type_origin = field_type_origin
                        field.field_type = field_type
                    if fkey_by_table_column.get('%s,%s' % (table_name, field_name)) is not None:
                        if field.field_type != field_type or field.foreign_table != foreign_table or \
                                field.foreign_column != foreign_column:
                            field.field_type = field_type
                            field.foreign_table = foreign_table
                            field.foreign_column = foreign_column
                    field_by_name[table_name].pop(field_name)

        self.close_cursor_db_odoo(cursor)

        return {
            'table_by_name': table_by_name,
            'field_by_name': field_by_name
        }

    def get_source_fields_db_odoo(self, **kwargs):
        self.ensure_one()

        cursor = self.get_cursor_db_odoo()

        Field = self.env['izi.table.field']

        table_by_name = kwargs.get('table_by_name')
        field_by_name = kwargs.get('field_by_name')
        fkey_by_table_column = self.get_foreignkey_field_db_odoo()

        # Get mapping oid and field type FROM pg_type
        typ_by_oid = {}
        cursor.execute("SELECT oid, typname FROM pg_type")
        dict_typs = self.dictfetchall_db_odoo(cursor)
        for typ in dict_typs:
            typ_by_oid[typ.get('oid')] = typ.get('typname')

        for table_name in table_by_name:

            table = table_by_name.get(table_name)

            if table.db_query is not False:
                table.get_table_fields()
                continue

            cursor.execute("SELECT * FROM %s LIMIT 1" % table_name)
            # Get and loop column description with env.cr.description from query given above
            for desc in cursor.description:
                field_name = desc.name
                field_title = field_name.replace('_', ' ').title()
                field_type_origin = typ_by_oid.get(desc.type_code)
                field_type = Field.get_field_type_mapping(field_type_origin, self.type)
                foreign_table = None
                foreign_column = None
                if fkey_by_table_column.get('%s,%s' % (table_name, field_name)) is not None:
                    fkey = fkey_by_table_column.get('%s,%s' % (table_name, field_name))
                    field_type = 'foreignkey'
                    foreign_table = fkey.get('foreign_table_name')
                    foreign_column = fkey.get('foreign_column_name')

                # Check to create or update field
                if field_name not in field_by_name[table_name]:
                    field = Field.create({
                        'name': field_title,
                        'field_name': field_name,
                        'field_type': field_type,
                        'field_type_origin': field_type_origin,
                        'table_id': table.id,
                        'foreign_table': foreign_table,
                        'foreign_column': foreign_column,
                    })
                else:
                    field = field_by_name[table_name][field_name]
                    if field.name != field_title or field.field_type_origin != field_type_origin or \
                            field.field_type != field_type:
                        field.name = field_title
                        field.field_type_origin = field_type_origin
                        field.field_type = field_type
                    if fkey_by_table_column.get('%s,%s' % (table_name, field_name)) is not None:
                        if field.field_type != field_type or field.foreign_table != foreign_table or \
                                field.foreign_column != foreign_column:
                            field.field_type = field_type
                            field.foreign_table = foreign_table
                            field.foreign_column = foreign_column
                    field_by_name[table_name].pop(field_name)

        self.close_cursor_db_odoo(cursor)

        return {
            'field_by_name': field_by_name
        }

    def check_query_db_odoo(self, **kwargs):
        query = kwargs.get('query')
        if query is False or query is None:
            return True

        escape_characters = ['\"', '\'', '\\', '\n', '\r', '\t', '\b', '\f']
        for char in escape_characters:
            query = query.replace(char, ' ')
        query = " ".join(query.split()).lower()

        forbidden_queries = ['drop database', 'drop schema', 'drop table', 'truncate table', 'delete from',
                             'delete user', 'select true']
        for forbidden_query in forbidden_queries:
            if forbidden_query in query.lower():
                raise ValidationError("Query is not allowed to contain '%s'" % forbidden_query)
