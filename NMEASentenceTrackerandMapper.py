import serial
import pynmea2
import folium
import threading
import queue
import time
from datetime import datetime, timedelta

class NMEATracker:
    def __init__(self, port='/dev/tty.usbmodem114103', baudrate=115200):
        """
        NMEAセンテンスを処理し、地図上に追跡するクラス
        
        Args:
            port (str): シリアルポート名
            baudrate (int): 通信速度
        """
        self.serial_port = None
        self.port = port
        self.baudrate = baudrate
        self.data_queue = queue.Queue()
        self.is_running = False
        self.processing_thread = None
        self.receive_thread = None
        
        # 座標と時刻を保存するリスト
        self.track_points = []
        
        # マップ作成
        self.map = folium.Map(location=[0, 0], zoom_start=2)

    def connect(self):
        """シリアルポートに接続"""
        try:
            self.serial_port = serial.Serial(
                port=self.port, 
                baudrate=self.baudrate,
                timeout=1
            )
            print(f"ポート {self.port} に接続しました")
        except serial.SerialException as e:
            print(f"接続エラー: {e}")
            return False
        return True

    def start_tracking(self):
        """データ受信と処理を開始"""
        if not self.serial_port:
            if not self.connect():
                return

        self.is_running = True
        
        # データ受信スレッド
        self.receive_thread = threading.Thread(target=self._receive_data)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        print("データ受信スレッド")
        
        # データ処理スレッド
        self.processing_thread = threading.Thread(target=self._process_data)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        print("データ処理スレッド")
        
    def stop_tracking(self):
        """トラッキングを停止"""
        self.is_running = False
        
        if self.receive_thread:
            self.receive_thread.join()
        if self.processing_thread:
            self.processing_thread.join()
        
        if self.serial_port:
            self.serial_port.close()
            print("シリアルポートを閉じました")
        
        # マップを保存
        self._save_map()

    def _receive_data(self):
        """シリアルポートからNMEAセンテンスを受信"""
        while self.is_running:
            try:
                if self.serial_port.in_waiting:
                    # データを1行読み込む（改行まで）
                    nmea_sentence = self.serial_port.readline().decode('utf-8').strip()
                    nmea_sentence = nmea_sentence.splitlines()
                    #if nmea_sentence:
                    for item in nmea_sentence:
                        nmea_sentence = "".join(nmea_sentence[0])
                        self.data_queue.put(nmea_sentence)
            except Exception as e:
                print(f"受信エラー: {e}")
                self.is_running = False

    def _process_data(self):       
        """受信したNMEAセンテンスを処理"""
        while self.is_running:
            try:
                # キューからデータを取得（タイムアウト付き）
                nmea_sentence = self.data_queue.get(timeout=1)
                
                # NMEAセンテンスをパース
                parsed_data = self._parse_nmea(nmea_sentence)
                
                # キューのタスク完了を通知
                self.data_queue.task_done()
            
            except queue.Empty:
                # キューが空の場合は少し待機
                time.sleep(0.1)
            except Exception as e:
                print(f"処理エラー: {e}")

    def _parse_nmea(self, nmea_sentence):
        """
        NMEAセンテンスをパースし、座標と時刻を抽出
        
        Args:
            nmea_sentence (str): NMEAセンテンス
        
        Returns:
            dict: パースされたデータ、または None
        """
        try:
            # GPSデータタイプを判定（主にGPGGAとGPRMCを処理）
            if nmea_sentence.startswith('$GNGGA') or nmea_sentence.startswith('$GNRMC'):
                # NMEAセンテンスをパース
                parsed = pynmea2.parse(nmea_sentence)
                
                # 位置情報を持つセンテンスの場合
                if hasattr(parsed, 'latitude') and hasattr(parsed, 'longitude'):
                    # 座標とタイムスタンプを抽出
                    latitude = parsed.latitude
                    longitude = parsed.longitude

                    # 時刻情報の抽出（異なるNMEAセンテンスで処理を分岐）
                    if hasattr(parsed, 'timestamp'):
                        timestamp = parsed.timestamp
                    elif hasattr(parsed, 'datetime'):
                        timestamp = parsed.datetime
                    else:
                        timestamp = datetime.now()
                    
                    # トラックポイントを保存
                    track_point = {
                        'latitude': latitude,
                        'longitude': longitude,
                        'timestamp': timestamp
                    }
                    self.track_points.append(track_point)
                    
                    # マップにマーカーを追加
                    self._update_map(track_point)
                    
                    print(f"座標: {latitude}, {longitude} - 時刻: {timestamp}")
                    
                return track_point
        
        except pynmea2.ParseError as e:
            print(f"NMEAセンテンスのパースエラー: {e}")
        except Exception as e:
            print(f"予期せぬエラー: {e}")
        
        return None

    def _update_map(self, track_point):
        """
        マップにトラックポイントを追加
        
        Args:
            track_point (dict): 座標と時刻情報
        """
        try:
            # 地図上にマーカーを追加
            folium.Marker(
                location=[track_point['latitude'], track_point['longitude']],
                popup=f"時刻: {track_point['timestamp']}",
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(self.map)
            
            # トラックポイントが2つ以上ある場合、ルートラインを描画
            if len(self.track_points) > 1:
                route_points = [[p['latitude'], p['longitude']] for p in self.track_points]
                folium.PolyLine(
                    route_points, 
                    color='blue', 
                    weight=2, 
                    opacity=0.8
                ).add_to(self.map)
        
        except Exception as e:
            print(f"マップ更新エラー: {e}")

    def _save_map(self):
        """
        追跡した位置情報を持つマップを保存
        """
        if self.track_points:
            # マップの中心を最後の位置に設定
            last_point = self.track_points[-1]
            self.map.location = [last_point['latitude'], last_point['longitude']]
            
            # マップを保存
            map_file = f"nmea_track_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            self.map.save(map_file)
            print(f"マップを {map_file} に保存しました")

def main():
    # NMEAトラッカーの初期化
    tracker = NMEATracker(
        port='/dev/tty.usbmodem114103',  # 実際のポート名に置き換える
        baudrate=115200         # 必要に応じて変更
    )
    
    try:
        # トラッキングの開始
        tracker.start_tracking()
        
        # メインスレッドを一定時間実行
        time.sleep(300)  # 例：5分間トラッキング
    
    except KeyboardInterrupt:
        print("トラッキングを中断します")
    
    finally:
        # トラッキングの停止
        tracker.stop_tracking()

if __name__ == '__main__':
    main()
