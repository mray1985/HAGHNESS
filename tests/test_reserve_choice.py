import unittest
from decimal import Decimal
from ha.connected.reserve import reserve_choice

class ReserveChoiceTests(unittest.TestCase):
    def test_default_and_intentional_extra_use_decimal_money(self):
        self.assertEqual(reserve_choice('25','no',''),(Decimal('0.25'),0))
        self.assertEqual(reserve_choice('17.25','yes','10.01'),(Decimal('0.1725'),1001))
        self.assertEqual(reserve_choice('0','yes','0.01'),(Decimal('0'),1))
        self.assertEqual(reserve_choice('100','no',''),(Decimal('1'),0))

    def test_invalid_or_unconsented_amounts_fail(self):
        cases=[('25','no','10'),('25','maybe','10'),('25','yes',''),('25','yes','0'),
               ('NaN','no',''),('Infinity','no',''),('101','no',''),('-1','no',''),
               ('1e1','no',''),('25.123','no',''),('25','yes','-1'),('25','yes','1.001'),
               ('25','yes','NaN'),('25','yes','1,000'),('25','yes','10000000000001')]
        for args in cases:
            with self.subTest(args=args),self.assertRaises(ValueError):reserve_choice(*args)
