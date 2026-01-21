# -*- coding: utf-8 -*-
import configparser
import os

class LanguageManager:
    """语言管理器，负责加载语言配置和提供翻译文本"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LanguageManager, cls).__new__(cls)
            cls._instance.config = configparser.ConfigParser()
            # 默认语言
            cls._instance.current_lang = 'chs' 
            # 默认语言文件目录
            cls._instance.lang_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'languages')
            cls._instance.load_language('chs')
        return cls._instance

    def load_language(self, lang_code):
        """加载指定语言的配置文件"""
        self.current_lang = lang_code
        file_map = {
            'chs': 'MDLang_chs.ini',
            'cht': 'MDLang_cht.ini',
            'en': 'MDLang_en.ini',
            # 其他语言...
        }
        
        file_name = file_map.get(lang_code, 'MDLang_chs.ini')
        file_path = os.path.join(self.lang_dir, file_name)
        
        if os.path.exists(file_path):
            try:
                # 使用 utf-8-sig 读取以处理 BOM
                self.config.read(file_path, encoding='utf-8-sig')
            except Exception as e:
                print(f"Error loading language file {file_path}: {e}")
                # Fallback to UTF-8
                self.config.read(file_path, encoding='utf-8')
        else:
            print(f"Language file not found: {file_path}")

    def tr(self, section, key, default=None):
        """获取翻译文本"""
        try:
            return self.config.get(section, key, fallback=default)
        except Exception:
            return default

# 全局单例
language_manager = LanguageManager()
