import pandas as pd
import glob
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import requests
from tqdm import tqdm
import zipfile  # 添加解压所需的模块

# 合并数据
def merge_csv_files(directory='data/BTCUSDT-15m/', output_file='data/merged_BTCUSDT-15m.csv'):
    try:
        csv_files = glob.glob(f'{directory}*.csv')
        if not csv_files:
            raise ValueError(f"目录 {directory} 中未找到 CSV 文件。")
        
        data_frames = []
        for file in csv_files:
            df = pd.read_csv(file, header=0)  # 指定header=0，跳过列名行
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

# 下载Binance数据
def download_binance_data(symbol='ETCUSDT', interval='15m', years=[2020], months=range(1, 13), save_dir='./data'):

    save_dir = f"{save_dir}/{symbol}_{interval}"
    os.makedirs(save_dir, exist_ok=True)
    
    base_url = f"https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/{interval}/"
    
    for year in years:
        for month in months:
            file_name = f"{symbol}-{interval}-{year}-{month:02d}.zip"
            url = base_url + file_name
            save_path = os.path.join(save_dir, file_name)
            
            if os.path.exists(save_path):
                print(f"已存在：{file_name}")
                continue
            
            try:
                print(f"开始下载 {file_name} ...")
                response = requests.get(url, stream=True)
                if response.status_code == 200:
                    total = int(response.headers.get('content-length', 0))
                    with open(save_path, 'wb') as file, tqdm(
                        desc=file_name, total=total, unit='B', unit_scale=True, ncols=100
                    ) as bar:
                        for chunk in response.iter_content(chunk_size=1024):
                            file.write(chunk)
                            bar.update(len(chunk))
                    print(f"✅ 下载完成: {file_name}")
                else:
                    print(f"❌ 无法访问 {file_name} (状态码: {response.status_code})")
            except Exception as e:
                print(f"下载失败 {file_name}: {e}")

# 解压Binance数据
def unzip_binance_data(symbol='ETCUSDT', interval='15m', save_dir='./data'):

    zip_dir = f"{save_dir}/{symbol}_{interval}"
    csv_dir = f"{save_dir}/{symbol}-{interval}"
    os.makedirs(csv_dir, exist_ok=True)
    
    zip_files = glob.glob(f"{zip_dir}/*.zip")
    if not zip_files:
        print(f"未找到zip文件在 {zip_dir}")
        return
    
    for zip_path in zip_files:
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(csv_dir)
            print(f"✅ 解压完成: {os.path.basename(zip_path)}")
        except Exception as e:
            print(f"解压失败 {zip_path}: {e}")

# 发送邮件提醒
def send_email_notification(
    subject,
    body,
    to_email='2160255989@qq.com',
    from_email='2243709509@qq.com',
    smtp_server='smtp.qq.com',
    smtp_port=587,
    smtp_user='2243709509@qq.com',
    smtp_password='xmvvfznyknrgdjja'
):
    try:
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        print("邮件发送成功。")
    except Exception as e:
        print(f"邮件发送失败：{e}")


