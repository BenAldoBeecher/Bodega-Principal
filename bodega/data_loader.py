import json
import os
from django.conf import settings

_DATA = None

def load_data():
    global _DATA
    if _DATA is None:
        path = os.path.join(settings.BASE_DIR, 'data.json')
        with open(path, 'r', encoding='utf-8') as f:
            _DATA = json.load(f)
    return _DATA

def get_usuarios():
    return load_data().get('usuarios', [])

def get_usuario_by_email(email):
    for u in get_usuarios():
        if u['email'].lower() == email.lower():
            return u
    return None

def get_usuario_by_id(uid):
    for u in get_usuarios():
        if u['id'] == uid:
            return u
    return None

def get_categorias():
    return load_data().get('categorias', [])

def get_categoria_by_id(cid):
    for c in get_categorias():
        if c['id'] == cid:
            return c
    return None

def get_ubicaciones():
    return load_data().get('ubicaciones', [])

def get_ubicacion_by_id(uid):
    for u in get_ubicaciones():
        if u['id'] == uid:
            return u
    return None

def get_productos():
    productos = load_data().get('productos', [])
    # Enriquecer con nombres de categoría y ubicación
    for p in productos:
        cat = get_categoria_by_id(p.get('categoria_id'))
        ubi = get_ubicacion_by_id(p.get('ubicacion_id'))
        p['categoria_nombre'] = cat['nombre'] if cat else '-'
        p['ubicacion_nombre'] = ubi['nombre'] if ubi else '-'
        p['alerta'] = p['stock'] <= p['stock_minimo']
    return productos

def get_producto_by_id(pid):
    for p in get_productos():
        if p['id'] == pid:
            return p
    return None

def get_proveedores():
    return load_data().get('proveedores', [])

def get_proveedor_by_id(pid):
    for p in get_proveedores():
        if p['id'] == pid:
            return p
    return None

def get_ingresos():
    ingresos = load_data().get('ingresos', [])
    for i in ingresos:
        prov = get_proveedor_by_id(i.get('proveedor_id'))
        user = get_usuario_by_id(i.get('usuario_id'))
        i['proveedor_nombre'] = prov['nombre'] if prov else '-'
        i['usuario_nombre'] = user['nombre'] if user else '-'
    return ingresos

def get_salidas():
    salidas = load_data().get('salidas', [])
    for s in salidas:
        user = get_usuario_by_id(s.get('usuario_id'))
        s['usuario_nombre'] = user['nombre'] if user else '-'
    return salidas

def get_productos_alerta():
    return [p for p in get_productos() if p['alerta']]

def get_stats():
    productos = get_productos()
    return {
        'total_productos': len(productos),
        'stock_bajo': len(get_productos_alerta()),
        'total_ingresos': len(get_ingresos()),
        'total_salidas': len(get_salidas()),
        'total_usuarios': len(get_usuarios()),
    }
