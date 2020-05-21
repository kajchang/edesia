import os
from pathlib import Path

from collections import OrderedDict

import colorama
from colorama import Fore

import json
from json import JSONDecodeError
import requests

from datetime import datetime

app_path = os.path.join(str(Path.home()), '.edesia')
api_key_path = os.path.join(app_path, 'api_key.txt')
daily_log_path = os.path.join(app_path, 'daily_logs')

colorama.init()


def color_text(color: str, text: str):
    return color + text + Fore.RESET


if not os.path.exists(app_path):
    # app init
    print(color_text(Fore.GREEN, 'Setting up...'))
    api_key = input('Enter an ' + color_text(Fore.BLUE, 'api.data.gov') + ' key: ')
    os.mkdir(app_path)
    os.mkdir(daily_log_path)
    with open(api_key_path, 'w') as api_key_file:
        api_key_file.write(api_key)
else:
    print(Fore.GREEN + 'Loading...' + Fore.RESET)
    with open(api_key_path, 'r') as api_key_file:
        api_key = api_key_file.read()


def get_daily_log_filename(date):
    return os.path.join(daily_log_path, date.strftime('%Y-%m-%d') + '.json')


def parse_amount_with_unit(amount_with_unit):
    amount = amount_with_unit.split()[0]
    unit = amount_with_unit[len(amount) + 1:]
    return amount, unit


def add_food_item():
    fdc_id = input(color_text(Fore.GREEN, 'FDC ID: ')).strip()
    resp = requests.get('https://api.nal.usda.gov/fdc/v1/food/' + fdc_id, params={
        'api_key': api_key
    })
    try:
        resp_json = resp.json()
    except JSONDecodeError:
        return print(color_text(Fore.RED, 'API Error Fetching Food'))

    portion_units = {}

    if resp_json['foodClass'] == 'Branded':
        portion_units[resp_json['servingSizeUnit']] = 100

        household_serving = resp_json['householdServingFullText']

        household_serving_amount, household_serving_unit = parse_amount_with_unit(household_serving)
        portion_units[household_serving_unit] = float(household_serving_amount) / resp_json['servingSize'] * 100

    if len(resp_json['foodPortions']) > 0:
        portion_units['g'] = 100
        for portion in resp_json['foodPortions']:
            portion_units[portion['modifier']] = 1 / (portion['gramWeight'] / portion['amount'] / 100)

    while True:
        amount_with_unit = input(color_text(Fore.GREEN, 'Amount (' + ' / '.join(portion_units) + '): ')).strip()
        amount, unit = parse_amount_with_unit(amount_with_unit)

        if unit not in portion_units:
            print(color_text(Fore.RED, 'Invalid Unit'))
            continue

        try:
            amount = float(amount)
        except ValueError:
            print(color_text(Fore.RED, 'Invalid Amount'))
            continue

        break

    meal_name = input(color_text(Fore.GREEN, 'Meal Name: ')).strip()

    portions_consumed = amount / portion_units[unit]
    consumed_nutrients = {}

    for nutrient in resp_json['foodNutrients']:
        if nutrient.get('amount') is not None:
            consumed_nutrients[nutrient['nutrient']['name']] = \
                [nutrient['amount'] * portions_consumed, nutrient['nutrient']['unitName']]

    data = {
        'fdc_id': fdc_id,
        'amount_with_unit': [amount, unit],
        'meal_name': meal_name,
        'nutrients': consumed_nutrients
    }

    with open(get_daily_log_filename(datetime.today()), 'a') as daily_log_file:
        daily_log_file.write(json.dumps(data))
        daily_log_file.write('\n')


def show_nutritional_summary():
    with open(get_daily_log_filename(datetime.today()), 'r') as daily_log_file:
        total_nutrients = {}

        for entry in daily_log_file.readlines():
            entry = json.loads(entry)
            for nutrient in entry['nutrients']:
                if total_nutrients.get(nutrient) is None:
                    total_nutrients[nutrient] = entry['nutrients'][nutrient]
                else:
                    total_nutrients[nutrient][0] += entry['nutrients'][nutrient][0]

    carbohydrate_amount = total_nutrients.get('Carbohydrate, by difference', [0])[0]
    fat_amount = total_nutrients.get('Total lipid (fat)', [0])[0]
    protein_amount = total_nutrients.get('Protein', [0])[0]

    calories = (carbohydrate_amount + protein_amount) * 4 + fat_amount * 9

    print(color_text(Fore.RED, 'Calories: {:.1f}'.format(calories)))

    print(color_text(Fore.YELLOW, 'Carbohydrates: {:.1f} g'.format(carbohydrate_amount)))
    print(color_text(Fore.GREEN, 'Protein: {:.1f} g'.format(protein_amount)))
    print(color_text(Fore.BLUE, 'Fat: {:.1f} g'.format(fat_amount)))


main_menu = OrderedDict((
    ('Add Food Item', [Fore.GREEN, add_food_item]),
    ('Show Nutritional Summary', [Fore.YELLOW, show_nutritional_summary])
))


def run_menu(menu):
    menu = OrderedDict((*menu.items(), ('Quit', [Fore.RED, lambda: None])))
    while True:
        for item_name in menu:
            print(
                color_text(menu[item_name][0], '[' + item_name[0].upper() + item_name[0].lower() + ']' + item_name[1:]))
        command = input('> ').strip()
        quitting = False
        for item_name in menu:
            if item_name.lower().startswith(command.lower()):
                if item_name == 'Quit':
                    quitting = True
                    break
                menu[item_name][1]()
        if quitting:
            break


run_menu(main_menu)
