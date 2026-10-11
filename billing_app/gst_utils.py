
from decimal import Decimal, ROUND_HALF_UP
import re

TWO_PLACES = Decimal('0.01')
ZERO_PLACES = Decimal('1')

def round_currency(amount: Decimal) -> Decimal:
    """Rounds amount to 2 decimal places using half-up method."""
    if amount is None:
        return Decimal('0.00')
    return Decimal(str(amount)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

def round_to_rupee(amount: Decimal) -> Decimal:
    """Rounds amount to nearest integer rupee under Section 170 of CGST Act."""
    if amount is None:
        return Decimal('0')
    return Decimal(str(amount)).quantize(ZERO_PLACES, rounding=ROUND_HALF_UP)


# Official GST slabs — Central Tax (Rate) Schedules (CGST Act, 2017)
VALID_GST_RATES = [
    Decimal('0.00'),
    Decimal('0.25'),
    Decimal('3.00'),
    Decimal('5.00'),
    Decimal('12.00'),
    Decimal('18.00'),
    Decimal('28.00'),
]

# Tax category constants
TAX_CATEGORY_TAXABLE   = 'TAXABLE'
TAX_CATEGORY_NIL_RATED = 'NIL_RATED'
TAX_CATEGORY_EXEMPT    = 'EXEMPT'
TAX_CATEGORY_NON_GST   = 'NON_GST'

TAX_CATEGORY_CHOICES = [
    (TAX_CATEGORY_TAXABLE,   'Standard Taxable Supply'),
    (TAX_CATEGORY_NIL_RATED, 'Nil-Rated Supply (0% Rate Schedule)'),
    (TAX_CATEGORY_EXEMPT,    'Exempt Supply (Section 11 Notification)'),
    (TAX_CATEGORY_NON_GST,   'Non-GST Supply (Outside GST Scope)'),
]

ZERO_TAX_CATEGORIES = {TAX_CATEGORY_NIL_RATED, TAX_CATEGORY_EXEMPT, TAX_CATEGORY_NON_GST}


# HSN Reference Catalogue — CBIC Central Tax Rate Notifications
# Rates may carry legal conditions (e.g. pre-packaged and labelled vs loose);
# items not listed must be verified and entered manually.
OFFICIAL_HSN_CATALOGUE = {
    '1006': {
        'description': 'Rice (Semi-milled or wholly milled, pre-packaged & labelled)',
        'category': 'Grains & Pulses',
        'gst_rate': Decimal('5.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule I, Entry 51',
    },
    '100610': {
        'description': 'Rice in the husk (Paddy) — Unbranded / Loose',
        'category': 'Grains & Pulses',
        'gst_rate': Decimal('0.00'),
        'tax_category': TAX_CATEGORY_EXEMPT,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 2/2017-CT(Rate), Entry 45',
    },
    '1512': {
        'description': 'Sunflower-seed oil and its fractions, edible grade',
        'category': 'Edible Oils',
        'gst_rate': Decimal('5.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule I, Entry 90',
    },
    '0401': {
        'description': 'Fresh milk and cream, not concentrated nor containing added sugar',
        'category': 'Dairy Products',
        'gst_rate': Decimal('0.00'),
        'tax_category': TAX_CATEGORY_EXEMPT,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 2/2017-CT(Rate), Entry 25',
    },
    '0402': {
        'description': 'Milk and cream, concentrated or sweetened (e.g., condensed milk)',
        'category': 'Dairy Products',
        'gst_rate': Decimal('12.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule II, Entry 8',
    },
    '0701': {
        'description': 'Potatoes, fresh or chilled',
        'category': 'Vegetables',
        'gst_rate': Decimal('0.00'),
        'tax_category': TAX_CATEGORY_NIL_RATED,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 2/2017-CT(Rate), Entry 38',
    },
    '0902': {
        'description': 'Tea, whether or not flavoured',
        'category': 'Beverages & Spices',
        'gst_rate': Decimal('5.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule I, Entry 40',
    },
    '0901': {
        'description': 'Coffee, roasted or decaffeinated, coffee husks and skins',
        'category': 'Beverages & Spices',
        'gst_rate': Decimal('5.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule I, Entry 39',
    },
    '1701': {
        'description': 'Cane or beet sugar and chemically pure sucrose in solid form',
        'category': 'Grocery',
        'gst_rate': Decimal('5.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule I, Entry 91',
    },
    '1905': {
        'description': 'Bread, pastry, cakes, biscuits and other bakers wares',
        'category': 'Bakery & Confectionery',
        'gst_rate': Decimal('18.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule III, Entry 16',
    },
    '2106': {
        'description': 'Food preparations not elsewhere specified or included',
        'category': 'Packaged Foods',
        'gst_rate': Decimal('18.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule III, Entry 23',
    },
    '2202': {
        'description': 'Waters, including mineral waters and aerated waters, containing added sugar',
        'category': 'Beverages',
        'gst_rate': Decimal('28.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('12.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Sch IV, Entry 12 & Compensation Cess Notification 1/2017',
    },
    '2710': {
        'description': 'Petroleum oils (Motor spirit / petrol, high speed diesel)',
        'category': 'Petroleum Products',
        'gst_rate': Decimal('0.00'),
        'tax_category': TAX_CATEGORY_NON_GST,
        'cess_rate': Decimal('0.00'),
        'notification': 'Section 9(2) CGST Act, 2017 (Non-GST Supply)',
    },
    '2208': {
        'description': 'Undenatured ethyl alcohol / Alcoholic liquor for human consumption',
        'category': 'Alcoholic Beverages',
        'gst_rate': Decimal('0.00'),
        'tax_category': TAX_CATEGORY_NON_GST,
        'cess_rate': Decimal('0.00'),
        'notification': 'Article 366(12A) Constitution of India (Non-GST Supply)',
    },
    '3004': {
        'description': 'Medicaments consisting of mixed or unmixed products for therapeutic uses',
        'category': 'Pharmaceuticals',
        'gst_rate': Decimal('12.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule II, Entry 61',
    },
    '3401': {
        'description': 'Soap; organic surface-active products and preparations for use as soap',
        'category': 'Personal Care',
        'gst_rate': Decimal('18.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule III, Entry 54',
    },
    '4820': {
        'description': 'Registers, account books, note books, order books, receipt books',
        'category': 'Stationery',
        'gst_rate': Decimal('12.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule II, Entry 123',
    },
    '6109': {
        'description': 'T-shirts, singlets and other vests, knitted or crocheted',
        'category': 'Apparel & Textiles',
        'gst_rate': Decimal('12.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule II, Entry 140',
    },
    '7108': {
        'description': 'Gold (including gold plated with platinum) unwrought or semi-manufactured',
        'category': 'Precious Metals',
        'gst_rate': Decimal('3.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule V, Entry 13',
    },
    '7102': {
        'description': 'Diamonds, whether or not worked, but not mounted or set (Rough diamonds)',
        'category': 'Precious Stones',
        'gst_rate': Decimal('0.25'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule VI, Entry 1',
    },
    '8471': {
        'description': 'Automatic data processing machines and units thereof; magnetic or optical readers',
        'category': 'Electronics & IT',
        'gst_rate': Decimal('18.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule III, Entry 360',
    },
    '8517': {
        'description': 'Telephone sets, smartphones, and other apparatus for transmission of voice/images',
        'category': 'Electronics & IT',
        'gst_rate': Decimal('18.00'),
        'tax_category': TAX_CATEGORY_TAXABLE,
        'cess_rate': Decimal('0.00'),
        'notification': 'Notification No. 1/2017-CT(Rate), Schedule III, Entry 368',
    },
}


def lookup_hsn(hsn_code: str):
    clean_hsn = re.sub(r'\D', '', str(hsn_code or ''))
    if not clean_hsn:
        return None

    if clean_hsn in OFFICIAL_HSN_CATALOGUE:
        data = OFFICIAL_HSN_CATALOGUE[clean_hsn].copy()
        data['hsn_code'] = clean_hsn
        data['is_verified'] = True
        return data

    # Try 4-digit prefix
    if len(clean_hsn) > 4 and clean_hsn[:4] in OFFICIAL_HSN_CATALOGUE:
        data = OFFICIAL_HSN_CATALOGUE[clean_hsn[:4]].copy()
        data['hsn_code'] = clean_hsn
        data['is_verified'] = True
        return data

    # Try 2-digit chapter
    if len(clean_hsn) > 2 and clean_hsn[:2] in OFFICIAL_HSN_CATALOGUE:
        data = OFFICIAL_HSN_CATALOGUE[clean_hsn[:2]].copy()
        data['hsn_code'] = clean_hsn
        data['is_verified'] = True
        return data

    return None


def validate_hsn_code(hsn_code: str) -> bool:
    """Returns True if HSN code consists of 2 to 8 numeric digits."""
    if not hsn_code:
        return False
    clean = re.sub(r'\s+', '', str(hsn_code))
    return bool(re.match(r'^\d{2,8}$', clean))


def calculate_gst_breakdown(
    price: Decimal,
    quantity: Decimal = Decimal('1'),
    gst_rate: Decimal = Decimal('0.00'),
    cess_rate: Decimal = Decimal('0.00'),
    tax_category: str = TAX_CATEGORY_TAXABLE,
    price_includes_gst: bool = False,
    is_interstate: bool = False,
    discount: Decimal = Decimal('0.00')
) -> dict:
    """
    Calculates accurate Indian GST breakdown for line items and totals.

    Rules applied:
      - Section 15 CGST Act: Taxable value = (Price * Quantity) - Discount.
      - If price_includes_gst is True:
          Taxable value = Gross Amount / (1 + (gst_rate + cess_rate) / 100)
      - Intra-State Supply (same State):
          CGST = Taxable value * (gst_rate / 200)
          SGST/UTGST = Taxable value * (gst_rate / 200)
          IGST = 0
      - Inter-State Supply (different State):
          IGST = Taxable value * (gst_rate / 100)
          CGST = 0
          SGST = 0
      - Compensation Cess = Taxable value * (cess_rate / 100)
      - Non-GST, Exempt, Nil-rated supplies: Tax rates and amounts are 0.
      - Precision: intermediate calculations use exact Decimals; output amounts rounded to 2 decimal places.
    """
    price = Decimal(str(price or 0))
    quantity = Decimal(str(quantity or 1))
    gst_rate = Decimal(str(gst_rate or 0))
    cess_rate = Decimal(str(cess_rate or 0))
    discount = Decimal(str(discount or 0))

    # Force 0% tax for non-taxable supply categories
    if tax_category in ZERO_TAX_CATEGORIES:
        gst_rate = Decimal('0.00')
        cess_rate = Decimal('0.00')

    gross_value = (price * quantity) - discount
    if gross_value < Decimal('0.00'):
        gross_value = Decimal('0.00')

    total_tax_rate = gst_rate + cess_rate

    if price_includes_gst and total_tax_rate > Decimal('0.00'):
        tax_factor = Decimal('1.00') + (total_tax_rate / Decimal('100.00'))
        taxable_value = gross_value / tax_factor
    else:
        taxable_value = gross_value

    taxable_val_rounded = round_currency(taxable_value)

    if is_interstate:
        cgst_rate = Decimal('0.00')
        sgst_rate = Decimal('0.00')
        igst_rate = gst_rate
        cgst_amount = Decimal('0.00')
        sgst_amount = Decimal('0.00')
        igst_amount = round_currency(taxable_val_rounded * (igst_rate / Decimal('100.00')))
    else:
        half_rate = gst_rate / Decimal('2.00')
        cgst_rate = half_rate
        sgst_rate = half_rate
        igst_rate = Decimal('0.00')
        cgst_amount = round_currency(taxable_val_rounded * (cgst_rate / Decimal('100.00')))
        sgst_amount = round_currency(taxable_val_rounded * (sgst_rate / Decimal('100.00')))
        igst_amount = Decimal('0.00')

    cess_amount = round_currency(taxable_val_rounded * (cess_rate / Decimal('100.00')))
    total_tax = cgst_amount + sgst_amount + igst_amount + cess_amount
    total_amount = round_currency(taxable_val_rounded + total_tax)

    return {
        'taxable_value': taxable_val_rounded,
        'gst_rate': gst_rate,
        'cgst_rate': cgst_rate,
        'cgst_amount': cgst_amount,
        'sgst_rate': sgst_rate,
        'sgst_amount': sgst_amount,
        'igst_rate': igst_rate,
        'igst_amount': igst_amount,
        'cess_rate': cess_rate,
        'cess_amount': cess_amount,
        'total_tax': total_tax,
        'total_amount': total_amount,
        'is_interstate': is_interstate,
        'price_includes_gst': price_includes_gst,
        'tax_category': tax_category,
    }
