import unittest

from audit.mask import mask


class MaskTest(unittest.TestCase):
    def test_mask_phone_email(self):
        self.assertEqual(mask("call 9811000001 or a.b@x.com"), "call [PHONE] or [EMAIL]")

    def test_mask_spaced_variants(self):
        self.assertEqual(mask("+91 98110-00001"), "[PHONE]")
        self.assertEqual(mask("car DL 3C AB 4521 sold"), "car [REG] sold")
        self.assertEqual(mask("UP16BT1234"), "[REG]")

    def test_mask_upi_and_challan(self):
        self.assertEqual(mask("paid to abc@okhdfc"), "paid to [UPI]")
        self.assertEqual(mask("challan DL81625240911123456"), "challan [CHALLAN_NO]")
        self.assertEqual(mask("aadhaar 1234 5678 9012"), "aadhaar [ID]")

    def test_mask_greeting_names(self):
        self.assertEqual(mask("Hi Rahul, sorry for the delay"), "Hi [NAME], sorry for the delay")
        self.assertEqual(mask("Dear Amit Kumar, we are checking"), "Dear [NAME], we are checking")
        self.assertEqual(mask("hello priya we checked"), "hello [NAME] we checked")

    def test_hinglish_hi_particle_untouched(self):
        self.assertEqual(mask("app ne bhara hi nahi"), "app ne bhara hi nahi")
        self.assertEqual(mask("Paid. Hi Rahul here"), "Paid. Hi [NAME] here")

    def test_mask_more_phone_and_id_shapes(self):
        self.assertEqual(mask("call 981-100-0001"), "call [PHONE]")
        self.assertEqual(mask("call 09811000001"), "call [PHONE]")
        self.assertEqual(mask("UTR 624113096497 done"), "UTR [ID] done")
        self.assertEqual(mask("paid to abc@axisbank"), "paid to [UPI]")
        self.assertEqual(mask("paid to abc@sbi"), "paid to [UPI]")

    def test_mask_reg_glued_lowercase(self):
        self.assertEqual(mask("car dl3cab1234 sold"), "car [REG] sold")

    def test_mask_none(self):
        self.assertEqual(mask(None), "")

    def test_plain_text_untouched(self):
        self.assertEqual(mask("paid 500 for challan in 2026"), "paid 500 for challan in 2026")


if __name__ == "__main__":
    unittest.main()
