# ==================== TVPlayer/main.py ====================
# 电视端视频播放器 - 主程序
# 支持电视台直播 + 电影点播
# =========================================================

import json
import os
import threading
import time
from datetime import datetime

import kivy
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.checkbox import CheckBox
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy.core.video import Video as CoreVideo
from kivy.network.urlrequest import UrlRequest
from kivy.utils import platform

kivy.require('2.3.0')

# 设置默认窗口大小（适配电视 1920x1080）
Window.size = (1920, 1080)
Window.clearcolor = (0.05, 0.05, 0.1, 1)

CONFIG_FILE = os.path.join(os.getcwd(), 'tv_config.json')


class ConfigManager:
    """配置管理器 - 保存/加载接口配置"""

    @staticmethod
    def load():
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            'live_channels': '',
            'live_enabled': False,
            'movie_api': '',
            'movie_enabled': False,
            'movie_category_api': '',
        }

    @staticmethod
    def save(config):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)


class VideoPlayerWidget(Widget):
    """视频播放器组件"""

    def __init__(self, url='', **kwargs):
        super().__init__(**kwargs)
        self.url = url
        self.video = None
        self.is_playing = False
        self._play_thread = None
        self._loading = True

        # 背景色块
        with self.canvas.before:
            self.bg_color = Color(0, 0, 0, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *x: setattr(self.bg_rect, 'pos', self.pos),
                  size=lambda *x: setattr(self.bg_rect, 'size', self.size))

        # 状态标签
        self.status_label = Label(
            text='📺 等待播放...',
            font_size='20sp',
            color=(0.7, 0.8, 1, 1),
            size_hint=(1, None),
            height=dp(40),
            halign='center',
            valign='middle',
            pos=(0, 0)
        )
        self.add_widget(self.status_label)

    def play(self, url=None):
        if url:
            self.url = url
        self.stop()
        self._loading = True
        self.status_label.text = f'⏳ 加载中...'
        self.status_label.color = (1, 0.8, 0.2, 1)
        self._play_thread = threading.Thread(target=self._do_play, args=(self.url,), daemon=True)
        self._play_thread.start()

    def _do_play(self, url):
        try:
            video = CoreVideo(source=url, loop=False, muted=False)
            video.play()

            def on_load(*args):
                self._loading = False

            def update_frame(dt):
                if self._loading or not video.texture:
                    return
                with self.canvas.before:
                    Color(1, 1, 1, 1)
                self.bg_rect.texture = video.texture
                video.next_frame()
                if video.state == 'stop':
                    Clock.unschedule(update_frame)
                    self._loading = True
                    Clock.schedule_once(lambda dt: self._on_video_stop(), 0.5)

            def check_state(dt):
                if video.state == 'playing' and self._loading:
                    self._loading = False
                    Clock.schedule_interval(update_frame, 1/24)
                    self.status_label.text = f'▶ 播放中: {url[:60]}...'
                    self.status_label.color = (0.3, 1, 0.3, 1)
                if video.state == 'stop' and not self._loading:
                    Clock.unschedule(update_frame)
                    self._loading = True
                    Clock.schedule_once(lambda dt: self._on_video_stop(), 1)

            Clock.schedule_interval(check_state, 0.5)
            video.bind(on_load=on_load)

        except Exception as e:
            Clock.schedule_once(lambda dt: self.status_label.setter('text')(
                self.status_label, f'❌ 播放失败: {str(e)[:80]}'))


    def _on_video_stop(self):
        self.status_label.text = '⏹ 播放结束'
        self.status_label.color = (1, 0.5, 0.5, 1)

    def stop(self):
        if self.video:
            try:
                self.video.stop()
            except Exception:
                pass
            self.video = None
        self._loading = True
        self.status_label.text = '⏹ 已停止'
        self.status_label.color = (0.8, 0.8, 0.8, 1)
        with self.canvas.before:
            Color(0, 0, 0, 1)


class ChannelCard(Button):
    """电视频道卡片"""

    def __init__(self, name, url, **kwargs):
        super().__init__(**kwargs)
        self.text = name
        self.url = url
        self.size_hint = (None, None)
        self.width = dp(200)
        self.height = dp(80)
        self.font_size = '18sp'
        self.background_color = (0.12, 0.12, 0.3, 1)
        self.color = (1, 1, 1, 1)
        self.focus_color = (0.3, 0.3, 0.7, 1)


class MovieCard(Button):
    """电影卡片"""

    def __init__(self, title, url='', **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.url = url
        self.size_hint = (None, None)
        self.width = dp(160)
        self.height = dp(220)
        self.font_size = '15sp'
        self.text = title if title else '未知'
        self.background_color = (0.08, 0.08, 0.22, 1)
        self.color = (1, 1, 1, 1)
        self.valign = 'bottom'


class SetupScreen(BoxLayout):
    """首次配置界面"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(60)
        self.spacing = dp(30)

        # 标题
        title = Label(
            text='📺 电视视频播放器',
            font_size='44sp', color=(0.8, 0.9, 1, 1),
            size_hint=(1, None), height=dp(70)
        )
        self.add_widget(title)

        subtitle = Label(
            text='首次使用，请先配置资源接口',
            font_size='22sp', color=(0.6, 0.7, 0.9, 1),
            size_hint=(1, None), height=dp(45)
        )
        self.add_widget(subtitle)

        # 分隔线
        divider = Widget(size_hint=(1, None), height=dp(2),
                         background_color=(0.3, 0.3, 0.6, 1))
        self.add_widget(divider)

        # 电视台配置
        live_group = BoxLayout(orientation='vertical', size_hint=(1, None), height=dp(190))
        live_group.add_widget(Label(
            text='📡 电视台直播接口', font_size='20sp',
            color=(0.7, 0.85, 1, 1), size_hint_y=None, height=dp(35)
        ))
        live_group.add_widget(Label(
            text='支持 m3u/m3u8 格式或 JSON API', font_size='13sp',
            color=(0.5, 0.6, 0.8, 1), size_hint_y=None, height=dp(22)
        ))
        self.live_input = TextInput(
            hint_text='输入电视台接口地址...',
            font_size='16sp', multiline=False,
            size_hint_y=None, height=dp(45),
            background_color=(0.1, 0.1, 0.2, 1),
            foreground_color=(1, 1, 1, 1)
        )
        live_group.add_widget(self.live_input)
        self.live_checkbox = CheckBox(active=False, size=(dp(28), dp(28)))
        live_group.add_widget(self.live_checkbox)
        self.add_widget(live_group)

        # 电影配置
        movie_group = BoxLayout(orientation='vertical', size_hint=(1, None), height=dp(190))
        movie_group.add_widget(Label(
            text='🎬 电影资源接口', font_size='20sp',
            color=(0.7, 0.85, 1, 1), size_hint_y=None, height=dp(35)
        ))
        movie_group.add_widget(Label(
            text='支持 JSON API 返回格式', font_size='13sp',
            color=(0.5, 0.6, 0.8, 1), size_hint_y=None, height=dp(22)
        ))
        self.movie_input = TextInput(
            hint_text='输入电影API接口地址...',
            font_size='16sp', multiline=False,
            size_hint_y=None, height=dp(45),
            background_color=(0.1, 0.1, 0.2, 1),
            foreground_color=(1, 1, 1, 1)
        )
        movie_group.add_widget(self.movie_input)
        self.movie_checkbox = CheckBox(active=False, size=(dp(28), dp(28)))
        movie_group.add_widget(self.movie_checkbox)
        self.add_widget(movie_group)

        # 按钮区域
        btn_layout = BoxLayout(size_hint=(1, None), height=dp(75), spacing=dp(20))
        self.save_btn = Button(
            text='💾 保存并进入', font_size='22sp',
            size_hint=(0.5, 1),
            background_color=(0.1, 0.4, 0.8, 1),
            color=(1, 1, 1, 1)
        )
        self.save_btn.bind(on_press=self.save_config)
        btn_layout.add_widget(self.save_btn)

        self.skip_btn = Button(
            text='⏭ 跳过配置', font_size='22sp',
            size_hint=(0.5, 1),
            background_color=(0.3, 0.3, 0.3, 1),
            color=(1, 1, 1, 1)
        )
        self.skip_btn.bind(on_press=self.skip_setup)
        btn_layout.add_widget(self.skip_btn)
        self.add_widget(btn_layout)

    def save_config(self, *args):
        config = {
            'live_channels': self.live_input.text.strip(),
            'live_enabled': self.live_checkbox.active,
            'movie_api': self.movie_input.text.strip(),
            'movie_enabled': self.movie_checkbox.active,
        }
        ConfigManager.save(config)
        App.get_running_app().switch_to_main()

    def skip_setup(self, *args):
        App.get_running_app().switch_to_main()


class LiveTVScreen(BoxLayout):
    """电视台直播界面"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(25)
        self.spacing = dp(15)

        # 顶部栏
        header = BoxLayout(size_hint=(1, None), height=dp(70), spacing=dp(15))
        back_btn = Button(text='🔙 返回', font_size='20sp',
                          size_hint=(None, 1), width=dp(130),
                          background_color=(0.15, 0.15, 0.35, 1),
                          color=(1, 1, 1, 1))
        back_btn.bind(on_press=lambda *a: App.get_running_app().show_screen('home'))
        header.add_widget(back_btn)
        header.add_widget(Label(
            text='📡 电视台直播', font_size='28sp',
            color=(0.8, 0.9, 1, 1), size_hint=(1, 1),
            halign='center', valign='middle'
        ))
        settings_btn = Button(text='⚙️', font_size='20sp',
                              size_hint=(None, 1), width=dp(60),
                              background_color=(0.15, 0.15, 0.35, 1),
                              color=(1, 1, 1, 1))
        settings_btn.bind(on_press=lambda *a: App.get_running_app().show_screen('settings'))
        header.add_widget(settings_btn)
        self.add_widget(header)

        # 频道列表
        scroll = ScrollView()
        self.channel_grid = GridLayout(cols=4, spacing=dp(12), size_hint_y=None)
        self.channel_grid.bind(minimum_height=self.channel_grid.setter('height'))
        scroll.add_widget(self.channel_grid)
        self.add_widget(scroll)

        # 底部播放器
        self.player = VideoPlayerWidget(size_hint=(1, None), height=dp(200))
        self.add_widget(self.player)

        self.channels = []
        self.load_channels()

    def load_channels(self):
        config = ConfigManager.load()
        url = config.get('live_channels', '')
        if not url:
            self.channel_grid.add_widget(Label(
                text='请先在设置中配置电视台接口',
                font_size='18sp', color=(0.8, 0.5, 0.5, 1)
            ))
            return

        self.channel_grid.clear_widgets()
        self.channels = []
        self.status_label = Label(
            text='🔄 加载中...', font_size='16sp',
            color=(0.6, 0.7, 0.9, 1), size_hint=(1, None), height=dp(30)
        )
        self.channel_grid.add_widget(self.status_label)

        req = UrlRequest(url, on_success=self._parse_channels,
                         on_error=self._load_error)

    def _parse_channels(self, req, data):
        try:
            text = data.decode('utf-8') if isinstance(data, bytes) else data
            channels = self._parse_m3u(text)
            if not channels:
                channels = self._parse_json(text)
        except Exception:
            channels = []

        self.status_label.destroy()
        self.status_label = None

        if not channels:
            self.channel_grid.add_widget(Label(
                text='未解析到频道，请检查接口格式',
                font_size='18sp', color=(0.8, 0.5, 0.5, 1)
            ))
            return

        self.channels = channels
        for name, url in channels:
            card = ChannelCard(name=name, url=url)
            card.bind(on_press=lambda *a, u=url: self.play_channel(u))
            self.channel_grid.add_widget(card)

    def _parse_m3u(self, text):
        channels = []
        lines = text.strip().split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('#EXTINF'):
                name = '未命名频道'
                parts = line.split(',')
                if len(parts) > 1:
                    name = parts[-1].strip()
                i += 1
                while i < len(lines) and not lines[i].strip():
                    i += 1
                if i < len(lines):
                    url = lines[i].strip()
                    if url and not url.startswith('#'):
                        channels.append((name, url))
            i += 1
        return channels

    def _parse_json(self, text):
        try:
            data = json.loads(text)
            channels = []
            if isinstance(data, list):
                for item in data:
                    name = item.get('name', item.get('title', item.get('channel', '未知')))
                    url = item.get('url', item.get('play_url', item.get('link', '')))
                    if url:
                        channels.append((str(name), url))
            elif isinstance(data, dict):
                for key, val in data.items():
                    if isinstance(val, str) and val.startswith(('http', '//')):
                        channels.append((key, val))
                    elif isinstance(val, dict):
                        url = val.get('url', val.get('play_url', val.get('link', '')))
                        if url:
                            channels.append((key, url))
            return channels
        except (json.JSONDecodeError, AttributeError):
            return []

    def _load_error(self, req, error):
        if self.status_label:
            self.status_label.destroy()
        self.channel_grid.add_widget(Label(
            text=f'加载失败: {error}',
            font_size='18sp', color=(0.8, 0.5, 0.5, 1)
        ))

    def play_channel(self, url):
        self.player.play(url)


class MovieScreen(BoxLayout):
    """电影点播界面"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(25)
        self.spacing = dp(15)

        # 顶部栏
        header = BoxLayout(size_hint=(1, None), height=dp(70), spacing=dp(15))
        back_btn = Button(text='🔙 返回', font_size='20sp',
                          size_hint=(None, 1), width=dp(130),
                          background_color=(0.15, 0.15, 0.35, 1),
                          color=(1, 1, 1, 1))
        back_btn.bind(on_press=lambda *a: App.get_running_app().show_screen('home'))
        header.add_widget(back_btn)
        header.add_widget(Label(
            text='🎬 电影点播', font_size='28sp',
            color=(0.8, 0.9, 1, 1), size_hint=(1, 1),
            halign='center', valign='middle'
        ))
        settings_btn = Button(text='⚙️', font_size='20sp',
                              size_hint=(None, 1), width=dp(60),
                              background_color=(0.15, 0.15, 0.35, 1),
                              color=(1, 1, 1, 1))
        settings_btn.bind(on_press=lambda *a: App.get_running_app().show_screen('settings'))
        header.add_widget(settings_btn)
        self.add_widget(header)

        # 搜索栏
        search_layout = BoxLayout(size_hint=(1, None), height=dp(55), spacing=dp(10))
        self.search_input = TextInput(
            hint_text='🔍 搜索电影...', font_size='16sp',
            multiline=False, size_hint=(0.6, 1),
            background_color=(0.1, 0.1, 0.2, 1),
            foreground_color=(1, 1, 1, 1)
        )
        search_layout.add_widget(self.search_input)
        self.refresh_btn = Button(
            text='🔄 刷新', font_size='16sp',
            size_hint=(0.3, 1),
            background_color=(0.1, 0.3, 0.6, 1),
            color=(1, 1, 1, 1)
        )
        self.refresh_btn.bind(on_press=lambda *a: self.load_movies())
        search_layout.add_widget(self.refresh_btn)
        self.add_widget(search_layout)

        # 电影列表
        scroll = ScrollView()
        self.movie_grid = GridLayout(cols=5, spacing=dp(12), size_hint_y=None)
        self.movie_grid.bind(minimum_height=self.movie_grid.setter('height'))
        scroll.add_widget(self.movie_grid)
        self.add_widget(scroll)

        # 底部播放器
        self.player = VideoPlayerWidget(size_hint=(1, None), height=dp(220))
        self.add_widget(self.player)

        self.movies = []
        self.load_movies()

    def load_movies(self, *args):
        config = ConfigManager.load()
        url = config.get('movie_api', '')
        if not url:
            self.movie_grid.clear_widgets()
            self.movie_grid.add_widget(Label(
                text='请先在设置中配置电影接口',
                font_size='18sp', color=(0.8, 0.5, 0.5, 1)
            ))
            return

        self.movie_grid.clear_widgets()
        self.movies = []

        loading_label = Label(
            text='🔄 加载中...', font_size='16sp',
            color=(0.6, 0.7, 0.9, 1), size_hint=(1, None), height=dp(30)
        )
        self.movie_grid.add_widget(loading_label)

        req = UrlRequest(url, on_success=self._parse_movies,
                         on_error=self._load_error)

    def _parse_movies(self, req, data):
        try:
            text = data.decode('utf-8') if isinstance(data, bytes) else data
            movies = self._parse_movie_json(text)
        except Exception:
            movies = []

        loading_label = None
        for child in list(self.movie_grid.children):
            if isinstance(child, Label) and child.text.startswith('🔄'):
                loading_label = child
                break
        if loading_label:
            loading_label.destroy()

        if not movies:
            self.movie_grid.add_widget(Label(
                text='未解析到电影数据',
                font_size='18sp', color=(0.8, 0.5, 0.5, 1)
            ))
            return

        self.movies = movies
        for movie in movies:
            card = MovieCard(title=movie['title'], url=movie.get('url', ''))
            card.bind(on_press=lambda *a, m=movie: self.play_movie(m))
            self.movie_grid.add_widget(card)

    def _parse_movie_json(self, text):
        try:
            data = json.loads(text)
            movies = []
            if isinstance(data, list):
                for item in data:
                    title = item.get('name', item.get('title',
                             item.get('vod_name', '未知')))
                    url = item.get('url', item.get('play_url',
                             item.get('vod_play_url',
                             item.get('link', item.get('playlink', '')))))
                    if url:
                        movies.append({'title': str(title), 'url': url})
            elif isinstance(data, dict):
                list_data = data.get('list', data.get('data',
                         data.get('videos', data)))
                if isinstance(list_data, list):
                    for item in list_data:
                        title = item.get('name', item.get('title',
                                 item.get('vod_name', '未知')))
                        url = item.get('url', item.get('play_url',
                                 item.get('link', '')))
                        if url:
                            movies.append({'title': str(title), 'url': url})
            return movies
        except (json.JSONDecodeError, AttributeError):
            return []

    def _load_error(self, req, error):
        loading_label = None
        for child in list(self.movie_grid.children):
            if isinstance(child, Label) and child.text.startswith('🔄'):
                loading_label = child
                break
        if loading_label:
            loading_label.destroy()
        self.movie_grid.add_widget(Label(
            text=f'加载失败: {error}',
            font_size='18sp', color=(0.8, 0.5, 0.5, 1)
        ))

    def play_movie(self, movie):
        self.player.play(movie.get('url', ''))


class SettingsScreen(BoxLayout):
    """设置界面"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(50)
        self.spacing = dp(25)

        # 标题
        title = Label(text='⚙️ 接口设置', font_size='36sp',
                      color=(0.8, 0.9, 1, 1),
                      size_hint=(1, None), height=dp(60))
        self.add_widget(title)

        config = ConfigManager.load()

        # 电视台接口
        live_layout = BoxLayout(orientation='vertical', size_hint=(1, None), height=dp(180))
        live_layout.add_widget(Label(text='📡 电视台接口地址', font_size='18sp',
                                      color=(0.7, 0.85, 1, 1), size_hint_y=None, height=dp(30)))
        self.live_input = TextInput(
            text=config.get('live_channels', ''),
            font_size='16sp', multiline=False,
            size_hint_y=None, height=dp(45),
            background_color=(0.1, 0.1, 0.2, 1),
            foreground_color=(1, 1, 1, 1)
        )
        live_layout.add_widget(self.live_input)
        self.live_check = CheckBox(active=config.get('live_enabled', False), size=(dp(28), dp(28)))
        live_layout.add_widget(self.live_check)
        self.add_widget(live_layout)

        # 电影接口
        movie_layout = BoxLayout(orientation='vertical', size_hint=(1, None), height=dp(180))
        movie_layout.add_widget(Label(text='🎬 电影API接口地址', font_size='18sp',
                                       color=(0.7, 0.85, 1, 1), size_hint_y=None, height=dp(30)))
        self.movie_input = TextInput(
            text=config.get('movie_api', ''),
            font_size='16sp', multiline=False,
            size_hint_y=None, height=dp(45),
            background_color=(0.1, 0.1, 0.2, 1),
            foreground_color=(1, 1, 1, 1)
        )
        movie_layout.add_widget(self.movie_input)
        self.movie_check = CheckBox(active=config.get('movie_enabled', False), size=(dp(28), dp(28)))
        movie_layout.add_widget(self.movie_check)
        self.add_widget(movie_layout)

        # 帮助说明
        help_text = Label(text=(
            '📖 使用说明\n'
            '• 电视台接口: 支持 .m3u / .m3u8 格式直播源\n'
            '• 电影接口: 支持 JSON API，返回视频列表\n'
            '• 遥控器操作: 方向键导航，OK键确认\n'
            '• 配置保存后在主页即可看到效果'
        ), font_size='15sp', color=(0.6, 0.7, 0.9, 1), size_hint=(1, None),
            height=dp(110), halign='left', valign='top')
        self.add_widget(help_text)

        # 按钮
        btn_layout = BoxLayout(size_hint=(1, None), height=dp(70), spacing=dp(15))
        save_btn = Button(text='💾 保存设置', font_size='22sp',
                           size_hint=(0.5, 1),
                           background_color=(0.1, 0.4, 0.8, 1),
                           color=(1, 1, 1, 1))
        save_btn.bind(on_press=self.save)
        btn_layout.add_widget(save_btn)

        back_btn = Button(text='🔙 返回主页', font_size='22sp',
                           size_hint=(0.5, 1),
                           background_color=(0.3, 0.3, 0.3, 1),
                           color=(1, 1, 1, 1))
        back_btn.bind(on_press=self.back)
        btn_layout.add_widget(back_btn)
        self.add_widget(btn_layout)

    def save(self, *args):
        config = {
            'live_channels': self.live_input.text.strip(),
            'live_enabled': self.live_check.active,
            'movie_api': self.movie_input.text.strip(),
            'movie_enabled': self.movie_check.active,
        }
        ConfigManager.save(config)
        App.get_running_app().show_screen('home')

    def back(self, *args):
        App.get_running_app().show_screen('home')


class HomeScreen(BoxLayout):
    """主界面"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(40)
        self.spacing = dp(20)

        # 标题
        title = Label(text='📺 电视视频播放器', font_size='40sp',
                      color=(0.8, 0.9, 1, 1),
                      size_hint=(1, None), height=dp(70))
        self.add_widget(title)

        time_label = Label(text='', font_size='16sp',
                           color=(0.5, 0.6, 0.8, 1),
                           size_hint=(1, None), height=dp(30))
        self.add_widget(time_label)

        def update_time(dt):
            time_label.text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        Clock.schedule_interval(update_time, 1)

        # 分隔线
        divider = Widget(size_hint=(1, None), height=dp(2),
                         background_color=(0.3, 0.3, 0.6, 1))
        self.add_widget(divider)

        # 功能按钮
        btn_layout = BoxLayout(orientation='vertical', size_hint=(1, 0.65),
                               spacing=dp(15), valign='middle')

        config = ConfigManager.load()
        has_live = bool(config.get('live_channels', '').strip())
        has_movie = bool(config.get('movie_api', '').strip())

        live_btn = Button(
            text=f'📡 电视台直播  {'✅' if has_live else '⚠️'}',
            font_size='28sp', size_hint=(1, None), height=dp(85),
            background_color=(0.1, 0.3, 0.6, 1) if has_live else (0.3, 0.15, 0.15, 1),
            color=(1, 1, 1, 1)
        )
        live_btn.bind(on_press=lambda *a: App.get_running_app().show_screen('live'))
        btn_layout.add_widget(live_btn)

        movie_btn = Button(
            text=f'🎬 电影点播  {'✅' if has_movie else '⚠️'}',
            font_size='28sp', size_hint=(1, None), height=dp(85),
            background_color=(0.1, 0.3, 0.6, 1) if has_movie else (0.3, 0.15, 0.15, 1),
            color=(1, 1, 1, 1)
        )
        movie_btn.bind(on_press=lambda *a: App.get_running_app().show_screen('movie'))
        btn_layout.add_widget(movie_btn)

        settings_btn = Button(
            text='⚙️ 接口设置',
            font_size='28sp', size_hint=(1, None), height=dp(85),
            background_color=(0.15, 0.15, 0.35, 1),
            color=(1, 1, 1, 1)
        )
        settings_btn.bind(on_press=lambda *a: App.get_running_app().show_screen('settings'))
        btn_layout.add_widget(settings_btn)

        self.add_widget(btn_layout)

        # 底部提示
        tip = Label(
            text='首次使用请先配置接口  |  支持 m3u/m3u8 直播源 + JSON API',
            font_size='14sp', color=(0.4, 0.5, 0.7, 1),
            size_hint=(1, None), height=dp(35),
            halign='center', valign='bottom'
        )
        self.add_widget(tip)


class TVPlayerApp(App):
    """主应用"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.screens = {}
        self.current_screen_name = 'setup'

    def build(self):
        self.screens = {
            'setup': SetupScreen(),
            'home': HomeScreen(),
            'live': LiveTVScreen(),
            'movie': MovieScreen(),
            'settings': SettingsScreen(),
        }
        self.root = self.screens['setup']
        self._check_config()

    def _check_config(self):
        config = ConfigManager.load()
        has_live = bool(config.get('live_channels', '').strip())
        has_movie = bool(config.get('movie_api', '').strip())
        if has_live or has_movie:
            self.root = self.screens['home']
            self.current_screen_name = 'home'
        else:
            self.root = self.screens['setup']
            self.current_screen_name = 'setup'

    def switch_to_main(self):
        self._check_config()

    def show_screen(self, name):
        if name in self.screens:
            self.root = self.screens[name]
            self.current_screen_name = name


if __name__ == '__main__':
    TVPlayerApp().run()