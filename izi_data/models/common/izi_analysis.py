# -*- coding: utf-8 -*-
# Copyright 2022 IZI PT Solusi Usaha Mudah
from odoo import models, fields, _, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class IZIAnalysis(models.Model):
    _name = 'izi.analysis'
    _description = 'IZI Analysis'

    name = fields.Char(string='Name', required=True)
    source_id = fields.Many2one('izi.data.source', string='Data Source', required=True, ondelete='cascade')
    table_id = fields.Many2one('izi.table', string='Table', required=True, ondelete='cascade')
    metric_ids = fields.One2many('izi.analysis.metric', 'analysis_id', string='Metrics', required=True)
    dimension_ids = fields.One2many('izi.analysis.dimension', 'analysis_id', string='Dimensions')
    filter_ids = fields.One2many('izi.analysis.filter', 'analysis_id', string='Filters')
    limit = fields.Integer('Limit')

    _sql_constraints = [
        ('name_table_unique', 'unique(name, table_id)', 'Name Already Exist.')
    ]

    def write(self, vals):
        for analysis in self:
            if 'table_id' in vals and vals['table_id'] != analysis.table_id.id:
                analysis.metric_ids.unlink()
                analysis.dimension_ids.unlink()
        res = super(IZIAnalysis, self).write(vals)
        return res

    def get_analysis_datas(self, **kwargs):
        self.ensure_one()
        if not self.metric_ids:
            raise ValidationError('To query the data, analysis must have at least one metric')

        res_data = []
        res_metrics = []
        res_dimensions = []
        res_fields = []
        res_values = []

        # query variable
        dimension_query = ''
        dimension_queries = []
        metric_query = ''
        metric_queries = []
        sort_query = ''
        sort_queries = []
        filter_query = "'IZI' = 'IZI'"
        filter_result_list = []

        max_dimension = False
        if 'max_dimension' in kwargs:
            max_dimension = kwargs.get('max_dimension')

        # Build Dimension Query
        func_get_field_metric_format = getattr(self, 'get_field_metric_format_%s' % self.source_id.type)
        func_get_field_dimension_format = getattr(self, 'get_field_dimension_format_%s' % self.source_id.type)
        func_get_field_sort = getattr(self, 'get_field_sort_format_%s' % self.source_id.type)
        count_dimension = 0
        for dimension in self.dimension_ids:
            dimension_alias = dimension.field_id.name
            if dimension.name_alias:
                dimension_alias = dimension.name_alias
            dimension_metric = func_get_field_metric_format(
                **{'field_name': dimension.field_id.field_name, 'field_type': dimension.field_id.field_type,
                   'field_format': dimension.field_format})
            dimension_field = func_get_field_dimension_format(
                **{'field_name': dimension.field_id.field_name, 'field_type': dimension.field_id.field_type,
                   'field_format': dimension.field_format})
            metric_queries.append('%s as "%s"' % (dimension_metric, dimension_alias))
            dimension_queries.append('%s' % (dimension_field))
            res_dimensions.append(dimension_alias)
            res_fields.append(dimension_alias)

            if dimension.sort:
                dimension_sort = func_get_field_sort(
                    **{'field_name': dimension.field_id.field_name, 'field_type': dimension.field_id.field_type,
                       'field_format': dimension.field_format, 'sort': dimension.sort})
                sort_queries.append(dimension_sort)

            count_dimension += 1
            if max_dimension:
                if count_dimension >= max_dimension:
                    break

        # Build Metric Query
        for metric in self.metric_ids:
            metric_alias = metric.field_id.name
            if metric.name_alias:
                metric_alias = metric.name_alias
            metric_queries.append('%s(%s) as "%s of %s"' % (metric.calculation,
                                  metric.field_id.field_name, metric.calculation.title(), metric_alias))
            if metric.sort:
                sort_queries.append('%s(%s) %s' % (metric.calculation, metric.field_id.field_name, metric.sort))
            res_metrics.append('%s of %s' % (metric.calculation.title(), metric_alias))
            res_fields.append('%s of %s' % (metric.calculation.title(), metric_alias))

        # Build Filter Query
        func_get_filter_query = getattr(self, 'get_filter_query_%s' % self.source_id.type)
        if 'filter_values' in kwargs:
            for filter_value in kwargs.get('filter_values'):
                result_query = func_get_filter_query(**{'filter_value': filter_value})
                filter_result_list.append(result_query)

        for filter_result in filter_result_list:
            if filter_result is False:
                continue

            filter_sub_query = False
            filter_sub_query = ' {join_operator} '.format(
                join_operator=filter_result.get('join_operator')).join(filter_result.get('query'))

            if filter_sub_query:
                filter_query += ' and (%s)' % filter_sub_query

        # Build Query
        # SELECT operation(metric) FROM table WHERE filter GROUP BY dimension ORDER BY sort
        metric_query = ', '.join(metric_queries)
        dimension_query = ', '.join(dimension_queries)
        table_query = self.table_id.table_name
        sort_query = ', '.join(sort_queries)

        # Check
        if self.table_id.db_query:
            table_query = '(%s) tbl_query' % (self.table_id.db_query)
            table_query = table_query.replace(';', '')
        if filter_query:
            filter_query = 'WHERE %s' % (filter_query)
        if dimension_query:
            dimension_query = 'GROUP BY %s' % (dimension_query)
        if sort_query:
            sort_query = 'ORDER BY %s' % (sort_query)

        query = '''
            SELECT %s
            FROM %s
            %s
            %s
            %s;
        ''' % (metric_query, table_query, filter_query, dimension_query, sort_query)

        func_check_query = getattr(self.source_id, 'check_query_%s' % self.source_id.type)
        func_check_query(**{
            'query': table_query,
        })

        func_get_analysis_datas = getattr(self, 'get_analysis_datas_%s' % self.source_id.type)
        result = func_get_analysis_datas(**{
            'query': query,
        })

        res_data = result.get('res_data')

        for record in res_data:
            res_value = []
            for key in record:
                res_value.append(record[key])
            res_values.append(res_value)

        result = {
            'data': res_data,
            'metrics': res_metrics,
            'dimensions': res_dimensions,
            'fields': res_fields,
            'values': res_values,
        }

        if 'test_analysis' not in self._context:
            return result
        else:
            title = _("Successfully Get Data Analysis")
            message = _("""
                Your analysis looks fine!
                Sample Data:
                %s
            """ % (str(result.get('data')[0]) if result.get('data') else str(result.get('data'))))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': title,
                    'message': message,
                    'sticky': False,
                }
            }

    def field_format_query(self, field_name, field_type, field_format):
        query = '%s' % (field_name)
        if not field_format:
            return query
        if field_type in ('date', 'datetime'):
            date_format = {
                'year': 'YYYY',
                'month': 'MON YYYY',
                'week': 'DD MON YYYY',
                'day': 'DD MON YYYY',
            }
            if field_format in date_format:
                query = '''to_char(date_trunc('%s', %s), '%s')''' % (
                    field_format, field_name, date_format[field_format])
        return query

    def get_date_range_by_date_format(self, date_format):
        # Today
        start_date = datetime.today()
        end_date = datetime.today()

        if date_format == 'this_week':
            start_date = start_date - timedelta(days=start_date.weekday())
            end_date = start_date + timedelta(days=6)
        elif date_format == 'last_10':
            start_date = start_date - timedelta(days=10)
        elif date_format == 'last_30':
            start_date = start_date - timedelta(days=30)
        elif date_format == 'last_60':
            start_date = start_date - timedelta(days=60)
        elif date_format == 'before_today':
            start_date = start_date.replace(year=start_date.year - 50)
            end_date = end_date - timedelta(days=1)
        elif date_format == 'after_today':
            start_date = start_date + timedelta(days=1)
            end_date = end_date.replace(year=end_date.year + 50)
        elif date_format == 'before_and_today':
            start_date = start_date.replace(year=start_date.year - 50)
        elif date_format == 'today_and_after':
            end_date = end_date.replace(year=end_date.year + 50)
        elif date_format == 'this_month':
            start_date = start_date.replace(day=1)
            next_month = start_date.replace(day=28) + timedelta(days=4)
            end_date = next_month - timedelta(days=next_month.day)
        elif date_format == 'last_month':
            start_date = start_date.replace(day=1) - timedelta(days=1)
            start_date = start_date.replace(day=1)
            next_month = start_date.replace(day=28) + timedelta(days=4)
            end_date = next_month - timedelta(days=next_month.day)
        elif date_format == 'last_two_months':
            next_month = start_date.replace(day=28) + timedelta(days=4)
            start_date = start_date.replace(day=1) - timedelta(days=1)
            start_date = start_date.replace(day=1)
            end_date = next_month - timedelta(days=next_month.day)
        elif date_format == 'last_three_months':
            next_month = start_date.replace(day=28) + timedelta(days=4)
            start_date = start_date.replace(day=1) - timedelta(days=1)
            start_date = start_date.replace(day=1) - timedelta(days=1)
            start_date = start_date.replace(day=1)
            end_date = next_month - timedelta(days=next_month.day)
        elif date_format == 'this_year':
            start_date = start_date.replace(day=1, month=1)
            end_date = end_date.replace(day=31, month=12)

        start_date = start_date.strftime("%Y-%m-%d") + ' 00:00:00'
        end_date = end_date.strftime("%Y-%m-%d") + ' 23:59:59'

        return {
            'start_date': start_date,
            'end_date': end_date,
        }


class IZIAnalysisMetric(models.Model):
    _name = 'izi.analysis.metric'
    _description = 'IZI Analysis Metric'
    _order = 'id'

    sequence = fields.Integer('Sequence')
    analysis_id = fields.Many2one('izi.analysis', string='Analysis', required=True, ondelete='cascade')
    table_id = fields.Many2one('izi.table', string='Table', related='analysis_id.table_id')
    field_id = fields.Many2one('izi.table.field', string='Field', required=True)
    field_type = fields.Char('Field Type', related='field_id.field_type')
    name = fields.Char('Name', related='field_id.name', store=True)
    name_alias = fields.Char(string="Alias")
    calculation = fields.Selection([
        ('count', 'Count'),
        ('sum', 'Sum'),
        ('avg', 'Avg'),
    ], string='Calculation', required=True, default='sum')
    sort = fields.Selection([
        ('asc', 'Ascending'),
        ('desc', 'Descending'),
    ], string='Sort', required=False, default=False)


class IZIAnalysisDimension(models.Model):
    _name = 'izi.analysis.dimension'
    _description = 'IZI Analysis Demension'
    _order = 'id'

    sequence = fields.Integer('Sequence')
    analysis_id = fields.Many2one('izi.analysis', string='Analysis', required=True, ondelete='cascade')
    table_id = fields.Many2one('izi.table', string='Table', related='analysis_id.table_id')
    field_id = fields.Many2one('izi.table.field', string='Field', required=True)
    field_type = fields.Char('Field Type', related='field_id.field_type')
    field_format = fields.Selection(selection=[
        ('day', 'Day'),
        ('week', 'Week'),
        ('month', 'Month'),
        ('year', 'Year'),
    ], string='Field Format')
    name = fields.Char('Name', related='field_id.name', store=True)
    name_alias = fields.Char(string="Alias")
    sort = fields.Selection([
        ('asc', 'Ascending'),
        ('desc', 'Descending'),
    ], string='Sort', required=False, default=False)


class IZIAnalysisFilter(models.Model):
    _name = 'izi.analysis.filter'
    _description = 'IZI Analysis Filter'

    analysis_id = fields.Many2one('izi.analysis', string='Analysis', required=True, ondelete='cascade')
    table_id = fields.Many2one('izi.table', string='Table', related='analysis_id.table_id')
    field_id = fields.Many2one('izi.table.field', string='Field', required=True)
    field_type = fields.Char('Field Type', related='field_id.field_type')
    type = fields.Selection(selection=[
        ('string_search', 'String Search'),
        ('date_range', 'Date Range'),
        ('date_format', 'Date Format'),
    ], string='Filter Type')
    name = fields.Char('Name', related='field_id.name', store=True)
