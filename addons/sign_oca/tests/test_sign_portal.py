# Copyright 2023 Dixmit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import json

from odoo.tests.common import HttpCase, tagged

from .common import SignOcaCommon


@tagged("post_install", "-at_install")
class TestSignPortal(SignOcaCommon, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Portal User",
                "login": "sign_oca_portal",
                "password": "sign_oca_portal",
                "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )
        cls.signer = cls.env["res.partner"].create({"name": "Signer"})
        cls.request = cls.env["sign.oca.request"].create(
            {
                "data": cls.data,
                "name": "Demo template",
                "signer_ids": [
                    (
                        0,
                        0,
                        {
                            "partner_id": cls.signer.id,
                            "role_id": cls.role_customer.id,
                        },
                    )
                ],
            }
        )
        cls.item = cls.request.add_item(
            {
                "role_id": cls.role_customer.id,
                "field_id": cls.env.ref("sign_oca.sign_field_name").id,
                "page": 1,
                "position_x": 10,
                "position_y": 10,
                "width": 10,
                "height": 10,
            }
        )
        cls.request.action_send()
        cls.env.flush_all()
        cls.request.signer_ids.invalidate_recordset()

    def test_portal(self):
        self.authenticate("sign_oca_portal", "sign_oca_portal")
        self.url_open(self.request.signer_ids.access_url).raise_for_status()
        self.assertEqual(
            base64.b64decode(self.data),
            self.url_open(
                f"/sign_oca/content/{self.request.signer_ids.id}/{self.request.signer_ids.access_token}"
            ).content,
        )
        self.assertEqual(
            self.url_open(
                f"/sign_oca/info/{self.request.signer_ids.id}/{self.request.signer_ids.access_token}",
                data="{}",
                headers={"Content-Type": "application/json"},
            ).json()["result"]["items"][str(self.item["id"])],
            self.item,
        )
        data = {}
        for key in self.request.signer_ids.get_info()["items"]:
            val = self.request.signer_ids.get_info()["items"][key].copy()
            val["value"] = "My Name"
            data[key] = val

    def _sign_from_portal(self):
        signer = self.request.signer_ids
        items = {}
        for key, item in signer.get_info()["items"].items():
            items[key] = dict(item, value="My Name")
        response = self.url_open(
            f"/sign_oca/sign/{signer.id}/{signer.access_token}",
            data=json.dumps({"params": {"items": items}}),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        self.assertNotIn("error", response.json())
        self.assertEqual(self.request.state, "2_signed")
        return signer

    def test_signed_page_without_copy(self):
        self.env.company.sign_oca_send_sign_request_copy = False
        signer = self._sign_from_portal()
        page = self.url_open(signer.access_url).text
        self.assertIn("The document has been signed.", page)
        self.assertNotIn("You should have received an email", page)
        self.assertIn(f"/sign_oca/content/{signer.id}/{signer.access_token}", page)

    def test_signed_page_with_copy(self):
        self.env.company.sign_oca_send_sign_request_copy = True
        signer = self._sign_from_portal()
        page = self.url_open(signer.access_url).text
        self.assertIn("You should have received an email", page)
