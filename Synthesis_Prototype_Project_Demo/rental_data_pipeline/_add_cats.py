from rentals.models import ApprovedEquipmentCategory

new_cats = ['Box Hopper', 'Bucket Truck', 'Float Switch', 'Picker', 'Rigging Equipment', 'Roller', 'Tank']
for name in new_cats:
    obj, created = ApprovedEquipmentCategory.objects.get_or_create(name=name)
    print(f'  {"Added" if created else "Exists"}: {name}')
print('Done.')
