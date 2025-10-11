import pandas as pd
import glob

# 合并数据
def merge_csv_files(directory='data/BTCUSDT-15m/', output_file='data/merged_BTCUSDT-15m.csv'):

    try:
        csv_files = glob.glob(f'{directory}*.csv')
        if not csv_files:
            raise ValueError(f"目录 {directory} 中未找到 CSV 文件。")
        
        data_frames = []
        for file in csv_files:
            df = pd.read_csv(file)
            data_frames.append(df)
        
        data = pd.concat(data_frames, ignore_index=True)
        data['open_time'] = pd.to_datetime(data['open_time'], unit='ms')
        data.sort_values('open_time', inplace=True)
        data.to_csv(output_file, index=False)
        print(f"合并完成，保存到 {output_file}，共 {len(data)} 行。")
        return data
    except Exception as e:
        print(f"合并出错：{e}")
        return None

# 加载和处理数据
def load_and_process_data(file_path='data/merged_BTCUSDT-15m.csv'):

    try:
        data = pd.read_csv(file_path)

        sample_value = str(data['open_time'].iloc[0]) if not data.empty else ''
        if sample_value.isdigit() and len(sample_value) == 13:
            data['open_time'] = pd.to_datetime(data['open_time'], unit='ms')
        else:
            data['open_time'] = pd.to_datetime(data['open_time'])
                
        data.set_index('open_time', inplace=True)
        data = data[['open', 'high', 'low', 'close', 'volume']].rename(
            columns={
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }
        )
        print(f"数据加载和处理完成，共 {len(data)} 行。")
        return data
    except Exception as e:
        print(f"数据加载和处理出错：{e}")
        return None

