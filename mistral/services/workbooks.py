# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from oslo.config import cfg

from mistral import context
from mistral.db.v1 import api as db_api_v1
from mistral.db.v2 import api as db_api_v2
from mistral.services import scheduler
from mistral.services import trusts
from mistral.workbook import parser as spec_parser


def create_workbook_v1(values):
    _add_security_info(values)

    return db_api_v1.workbook_create(values)


def update_workbook_v1(workbook_name, values):
    wb_db = db_api_v1.workbook_update(workbook_name, values)

    if 'definition' in values:
        scheduler.create_associated_triggers(wb_db)

    return wb_db


def create_workbook_v2(values):
    _add_security_info(values)

    db_api_v2.start_tx()

    try:
        wb_db = db_api_v2.create_workbook(values)

        _check_workbook_definition_update(wb_db, values)

        db_api_v2.commit_tx()
    finally:
        db_api_v2.end_tx()

    return wb_db


def update_workbook_v2(workbook_name, values):
    db_api_v2.start_tx()

    try:
        wb_db = db_api_v1.workbook_update(workbook_name, values)

        _check_workbook_definition_update(wb_db, values)

        db_api_v2.commit_tx()
    finally:
        db_api_v2.end_tx()

    return wb_db


def _check_workbook_definition_update(wb_db, values):
    if 'definition' not in values:
        return

    wb_spec = spec_parser.get_workbook_spec_from_yaml(values['definition'])

    _create_actions(wb_db, wb_spec.get_actions())
    _create_workflows(wb_db, wb_spec.get_workflows())


def _create_actions(wb_db, actions_spec):
    if actions_spec:
        # TODO(rakhmerov): Complete when action DB model is added.
        pass


def _create_workflows(wb_db, workflows_spec):
    if workflows_spec:
        for wf_spec in workflows_spec:
            db_api_v2.create_workflow(
                {
                    'name': '%s.%s' % (wb_db.name, wf_spec.get_name()),
                    'spec': wf_spec.to_dict(),
                    'scope': wb_db.scope,
                    'trust_id': wb_db.trust_id,
                    'project_id': wb_db.project_id
                }
            )


def _add_security_info(values):
    if cfg.CONF.pecan.auth_enable:
        values.update({
            'trust_id': trusts.create_trust().id,
            'project_id': context.ctx().project_id
        })
