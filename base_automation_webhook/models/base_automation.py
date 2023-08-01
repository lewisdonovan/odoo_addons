# Copyright 2019 Ivan Yelizariev <https://it-projects.info/team/yelizariev>
# License MIT (https://opensource.org/licenses/MIT).
# Forked 2023 by Lewis Donovan <https://lewisdonovan.dev>

import json
import logging
from datetime import datetime, date
import requests

# The file name is incorrect and should be called ir_actions_server.py instead
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class OdooJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, models.BaseModel):
            return obj.read()[0]
        elif isinstance(obj, str) and obj in self.env:
            Model = self.env[obj]
            return Model.read()[0]
        elif isinstance(obj, fields.Many2one):
            return obj.sudo().read()[0]
        elif isinstance(obj, int):
            return int(obj)
        elif isinstance(obj, float):
            return float(obj)
        elif isinstance(obj, bool):
            return bool(obj)
        elif isinstance(obj, fields.Selection):
            return obj.get_obj().display_name
        elif isinstance(obj, (fields.Char, fields.Text)):
            return obj
        elif isinstance(obj, (fields.One2many, fields.Many2many)):
            return obj.read()
        elif isinstance(obj, bytes):
            return obj.decode('utf-8')
        return super().default(obj)

class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    def get_nested_field_data(self, entry_ids, related_model_name):
        entry = self.env[related_model_name].browse(entry_ids)
        return entry.read()

    @api.model
    def _get_eval_context(self, action=None, http_request=None):
        eval_context = super(IrActionsServer, self)._get_eval_context(action)
        eval_context["make_request"] = self.make_request
        eval_context["get_nested_field_data"] = self.get_nested_field_data
        eval_context['request'] = http_request
        return eval_context

    def convert_datetime_to_str(self, data):
        def json_serial(obj):
            if isinstance(obj, (datetime, date)):
                return obj.strftime('%Y-%m-%d %H:%M:%S')
            raise TypeError("Type not serializable")

        return json.loads(json.dumps(data, default=json_serial))

    @api.model
    def make_request(self, method, url, record, max_depth=3):
        headers = {'Content-Type': 'application/json'}
        try:
            if len(record) == 1:
                record_data = record.read()[0]
            else:
                record_data = []
                for rec in record:
                    record_data.append(rec.read())

            relational_fields = [field for field in record._fields if record._fields[field].type.lower() in ['many2one', 'one2many', 'many2many']]
            for field_name in relational_fields:
                if record_data[field_name] and field_name != "id":
                    related_model_name = record._fields[field_name].comodel_name
                    field_value = record_data[field_name]
                    field_value_type = type(field_value)
                    if field_value_type == list:
                        entry_ids = field_value
                    elif field_value_type == int:
                        entry_ids = [field_value]
                    elif field_value_type == tuple:
                        entry_ids = [field_value[0]]
                    else:
                        _logger.warning("Unsupported field value type for field '%s': %s. Skipping...", field_name, field_value_type)
                        continue
                    nested_data = self.get_nested_field_data(entry_ids, related_model_name)
                    record_data[field_name] = nested_data

            payload_data = json.loads(json.dumps(record_data, cls=OdooJSONEncoder))
            payload_data = self.convert_datetime_to_str(payload_data)

        except Exception as e:
            payload_data = json.dumps({'error': str(e)}, cls=OdooJSONEncoder)

        try:
            requests.request(method, url, data=json.dumps(payload_data), headers=headers)
        except Exception as e:
            _logger.error("Error making request: %s", e)
