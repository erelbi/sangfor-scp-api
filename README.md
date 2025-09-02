# Sangfor API İstemcisi v0.0.1 (cilbir edition)

[![Python Version](https://img.shields.io/badge/python-3.6%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> *Bizi Çin teknolojisi ile tanıştıran Onur Çılbır'ın anısına, 0.0.x versiyonları "cilbir edition" olarak yayınlanacaktır.*


Bu Python kütüphanesi, Sangfor HCI ve SCP (Sangfor Cloud Platform) platformlarının Open-API'si ile etkileşim kurmak için geliştirilmiştir. Kimlik doğrulama işlemleri için AWS Signature V4 benzeri bir imzalama metodolojisi kullanır.

##  Özellikler

* Tüm API istekleri için otomatik kimlik doğrulama ve imzalama.
* Kullanılabilirlik Alanlarını (Availability Zones) listeleme.
* Sanal makineleri sayfalama desteğiyle listeleme veya tümünü tek seferde getirme.
* ID veya isme göre belirli bir sanal makineyi bulma ve detaylarını getirme.
* Sanal makinelerin anlık görüntülerini (snapshots) ve yedeklerini (backups) sorgulama.
* Tüm altyapı için kaynak kullanımını özetleyen genel bir rapor oluşturma.
* Hata ayıklama için ayrıntılı (`verbose`) mod.

##  Kurulum

Bu proje, standart bir Python paketi olarak yapılandırılmıştır. Kurulum için projenin ana dizininde aşağıdaki komutu çalıştırmanız yeterlidir. Bu komut, `requests` gibi bağımlılıkları da otomatik olarak yükleyecektir.

```bash
# Projenin ana dizinindeyken (pyproject.toml dosyasının olduğu yerde)
pip install .
```

##  Kullanım

### 1. İstemciyi Başlatma

Paketi kurduktan sonra, herhangi bir Python script'inden `SangforSDKClient` sınıfını import edebilirsiniz.

```python
from sangfor_sdk.client import SangforSDKClient

# --- Yapılandırma ---
ACCESS_KEY = "SIZIN_ERISIM_ANAHTARINIZ"
SECRET_KEY = "SIZIN_GIZLI_ANAHTARINIZ"
REGION = "GOLBASI"
SERVICE = "open-api" # Genellikle 'open-api' 
BASE_URL = "https://<IP_VEYA_HOSTNAME>:PORT"

# Hata ayıklama için verbose=True parametresini ekleyebilirsiniz.
client = SangforSDKClient(
    access_key=ACCESS_KEY,
    secret_key=SECRET_KEY,
    region=REGION,
    service=SERVICE,
    base_url=BASE_URL,
    verbose=True
)
```

### 2. Temel Fonksiyon Örnekleri

```python
import json

# Kullanılabilirlik Alanlarını Listele
az_list = client.get_availability_zones()
print("--- Kullanılabilirlik Alanları ---")
print(json.dumps(az_list, indent=2))

# Tüm Sanal Makineleri Listele
all_vms = client.get_all_vms()
print(f"\n--- Toplam {len(all_vms)} Sanal Makine Bulundu ---")

# Belirli Bir Sanal Makineyi İsmiyle Bul
vm_name = "test-web-server-01"
vm_details = client.find_vm(vm_name)
print(f"\n--- '{vm_name}' Arama Sonucu ---")
if vm_details:
    print(json.dumps(vm_details, indent=2))
else:
    print(f"'{vm_name}' adında bir sanal makine bulunamadı.")
```

### 3. Pratik Kullanım Script'i (`report_generator.py`)

Aşağıdaki örnek, paketi kurduktan sonra altyapı raporu oluşturmak için bağımsız bir script'in nasıl yazılabileceğini gösterir.

```python
# report_generator.py

import json
# Kurulum sonrası paketi doğru şekilde import ediyoruz
from sangfor_sdk.client import SangforSDKClient 

def main():
    """
    Altyapı raporunu oluşturan ve JSON olarak yazdıran ana fonksiyon.
    """
    # --- API Bilgileri ---
    # Bu bilgileri güvenli bir yerden (örn: environment variables) okumanız önerilir.
    ACCESS_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    SECRET_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    REGION = "GOLBASI"
    SERVICE = "open-api"
    BASE_URL = "[https://IP:PORT]"
    
    print("API istemcisi oluşturuluyor...")
    
    try:
        # SDK istemcisini başlat (verbose=True ile istek/yanıt detaylarını görebilirsiniz)
        client = SangforSDKClient(ACCESS_KEY, SECRET_KEY, REGION, SERVICE, BASE_URL, verbose=True)
        
        print("İstemci başarıyla oluşturuldu. Altyapı raporu isteniyor...")
        
        # SDK'daki raporlama fonksiyonunu çağır
        infrastructure_report = client.generate_infrastructure_report()
        
        if infrastructure_report:
            print("\n--- Altyapı Genel Raporu ---")
            # JSON çıktısını daha okunaklı hale getirmek için indent kullanılır
            print(json.dumps(infrastructure_report, indent=2, ensure_ascii=False))
        else:
            print("\nHATA: Rapor oluşturulamadı. Sunucudan geçerli bir yanıt alınamadı.")

    except ImportError:
        print("\nHATA: Paket bulunamadı. Lütfen 'pip install .' komutuyla kurulum yaptığınızdan emin olun.")
    except Exception as e:
        print(f"\nBEKLENMEDİK HATA: Program çalışırken bir hata oluştu: {e}")

if __name__ == '__main__':
    main()

```

Bu script'i çalıştırmak için:
1.  Önce yukarıdaki "Kurulum" bölümündeki gibi `pip install .` komutuyla paketi kurun.
2.  `report_generator.py` dosyasını **proje dizininin dışında** herhangi bir yere kaydedin.
3.  Terminalden `python report_generator.py` komutunu çalıştırın.

##  Hata Yönetimi

* **Bağlantı Hataları:** SDK, `requests.exceptions.RequestException` gibi ağ hatalarını yakalar ve konsola bir hata mesajı yazdırarak `None` döndürür.
* **API Hataları:** API'den 4xx veya 5xx gibi bir HTTP hata kodu döndüğünde, SDK bu hatayı yakalar ve API'nin döndürdüğü JSON formatındaki hata mesajını size geri verir. `verbose=True` modunda, hata detayı ve sunucu yanıtı konsola yazdırılır.

##  Lisans

Bu proje MIT Lisansı altında lisanslanmıştır.