"""New user settings API blueprint."""
from __future__ import annotations
from flask import Blueprint, jsonify

bp = Blueprint('new_user_api', __name__)

@bp.get('/api/new_user')
def new_user_settings():
    """
    返回新用户的初始设置
    包括各个 plan 的默认选项卡片选择数量
    """
    return jsonify({
        'options_card_sel_number': {
            '20P': {
                'backdrops': 3,
                'hairstyles': 3,
                'poses': 3,
                'outfits': 3
            },
            '40P': {
                'backdrops': 5,
                'hairstyles': 5,
                'poses': 5,
                'outfits': 5
            },
            '80P': {
                'backdrops': 8,
                'hairstyles': 8,
                'poses': 8,
                'outfits': 8
            }
        }
    })
