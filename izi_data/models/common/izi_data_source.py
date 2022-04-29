# -*- coding: utf-8 -*-
# Copyright 2022 IZI PT Solusi Usaha Mudah
from odoo import models, fields


class IZIDataSource(models.Model):
    _name = 'izi.data.source'
    _description = 'IZI Data Source'

    name = fields.Char(string='Name', required=True)
    type = fields.Selection([], string='Type')
    table_ids = fields.One2many('izi.table', 'source_id', string='Tables')
    table_filter = fields.Char('Table Filter')
    state = fields.Selection([('new', 'New'), ('ready', 'Ready')], default='new', string='State')
    # TODO: username, password fields?

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Name Already Exist.')
    ]

    def authenticate(self):
        func = getattr(self, 'authenticate_%s' % self.type)
        return func()

    def get_source_tables(self):
        self.ensure_one()

        Table = self.env['izi.table']
        Field = self.env['izi.table.field']

        # Get existing table and field
        table_by_name = {}
        field_by_name = {}
        for izi_table in Table.search(['|', ('source_id', '=', self.id), ('db_query', '!=', False)]):
            table_name = izi_table.table_name
            if table_name is False:
                table_name = (izi_table.name.replace(' ', '_') + '_' + self.type).lower()
            table_by_name[table_name] = izi_table
            field_by_name[table_name] = {}
            for izi_field in Field.search([('table_id', '=', izi_table.id)]):
                field_by_name[table_name][izi_field.field_name] = izi_field

        # Table Filter
        table_filter_query = ''
        if self.table_filter:
            table_filters = []
            for table_filter in self.table_filter.split(','):
                table_filters.append('$$%s$$' % table_filter)
            table_filter_query = ','.join(table_filters)
            table_filter_query = 'AND table_name IN (%s)' % table_filter_query

        func_get_source_tables = getattr(self, 'get_source_tables_%s' % self.type)
        result = func_get_source_tables(**{
            'table_by_name': table_by_name,
            'field_by_name': field_by_name,
            'table_filter_query': table_filter_query,
        })

        table_by_name = result.get('table_by_name')
        field_by_name = result.get('field_by_name')

        for table_name in field_by_name:
            for field_name in field_by_name[table_name]:
                if field_by_name[table_name][field_name].table_id.db_query is not False:
                    continue
                for dimension in field_by_name[table_name][field_name].analysis_dimension_ids:
                    dimension.unlink()
                for metric in field_by_name[table_name][field_name].analysis_metric_ids:
                    metric.unlink()
                field_by_name[table_name][field_name].unlink()
        for table_name in table_by_name:
            if table_by_name[table_name].db_query is not False:
                table_by_name[table_name].get_table_fields()
                continue
            table_by_name[table_name].unlink()

    def get_source_fields(self):
        self.ensure_one()

        Table = self.env['izi.table']
        Field = self.env['izi.table.field']

        # Table Filter
        table_filter_query = []
        if self.table_filter:
            for table_filter in self.table_filter.split(','):
                table_filter_query.append(table_filter)

        # Get existing table and field
        table_by_name = {}
        field_by_name = {}
        table_search_domain = ['|', ('source_id', '=', self.id), ('db_query', '!=', False)]
        if table_filter_query:
            table_search_domain = [('source_id', '=', self.id), '|', ('db_query', '!=', False),
                                   ('table_name', 'in', table_filter_query)]
        for izi_table in Table.search(table_search_domain):
            table_name = izi_table.table_name
            if table_name is False:
                table_name = (izi_table.name.replace(' ', '_') + '_' + self.type).lower()
            table_by_name[table_name] = izi_table
            field_by_name[table_name] = {}
            for izi_field in Field.search([('table_id', '=', izi_table.id)]):
                field_by_name[table_name][izi_field.field_name] = izi_field

        func_get_source_fields = getattr(self, 'get_source_fields_%s' % self.type)
        result = func_get_source_fields(**{
            'table_by_name': table_by_name,
            'field_by_name': field_by_name,
        })

        field_by_name = result.get('field_by_name')

        for table_name in field_by_name:
            for field_name in field_by_name[table_name]:
                if field_by_name[table_name][field_name].table_id.db_query is not False:
                    continue
                for dimension in field_by_name[table_name][field_name].analysis_dimension_ids:
                    dimension.unlink()
                for metric in field_by_name[table_name][field_name].analysis_metric_ids:
                    metric.unlink()
                field_by_name[table_name][field_name].unlink()
