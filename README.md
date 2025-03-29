NMEAセンテンスのGNGGA, GNRMCのから座標を取り出して地図上にプロット。

受信が止まると同じディレクトリにhtmlファイルが生成される。

データがひたすら流れてくる場合、jupyter notebook では停止ボタン、コンソールでpython script を実行している場合は control + C で止めてhtmlが生成される。

時刻はUTCなので注意。datetime.timeをJSTにうまく変換する方法がわからなかった。
