# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    name = fields.Char(compute="get_name", inverse='reverse_name', store=True, readonly=False)
    first_name = fields.Char("First name")
    last_name = fields.Char("Last name")

    _sql_constraints = [("check_name", "CHECK( 1=1 )", "Contacts require a name.")]

    @api.depends("first_name", "last_name")
    def get_name(self):
        for record in self:
            record.name = " ".join(n for n in (record.first_name, record.last_name) if n)

    @api.model
    def create(self, vals):
        ctx = dict(self.env.context)
        t_name = vals.get("name", ctx.get("default_name"))
        if t_name is not None:
            new_inv_name = self.get_reverse_name(self.new_modified_name(t_name))
            for key, value in new_inv_name.items():
                if not vals.get(key):
                    vals[key] = value
            if "name" in vals:
                del vals["name"]
            if "default_name" in ctx:
                del ctx["default_name"]

        return super(ResPartner, self.with_context(ctx)).create(vals)

    @api.model
    def new_modified_name(self, name):
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        try:
            name = " ".join(name.split()) if name else name
        except UnicodeDecodeError:
            name = " ".join(name.decode("utf-8").split()) if name else name
        return name

    def reverse_name(self):
        for record in self:
            record.name = record.new_modified_name(record.name)
            record.revert_name()

    @api.model
    def get_reverse_name(self, name):
        sequence = 'fl'
        portion = name.split("," if sequence == "lfc" else " ", 1)
        if len(portion) > 1:
            if sequence == "fl":
                portion = [" ".join(portion[1:]), portion[0]]
            else:
                portion = [portion[0], " ".join(portion[1:])]
        else:
            while len(portion) < 2:
                portion.append(False)
        if len(portion) == 2:
            if not portion[1]:
                res = {"last_name": portion[1], "first_name": portion[0]}
            else:
                res = {"last_name": portion[0], "first_name": portion[1]}
            return res

    def revert_name(self):
        for record in self:
            portion = record.get_reverse_name(record.name)
            record.last_name = portion["last_name"]
            record.first_name = portion["first_name"]
