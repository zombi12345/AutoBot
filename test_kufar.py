from kufar_finder_core import KufarClient, KufarConfig

# 2010 = Легковые автомобили (по данным ReefAPI)
config = KufarConfig.from_env(categories=("2010",))
with KufarClient(config) as client:
    ads = client.fetch_ads(min_price=0, max_price=50000)  # BYN
    print(f"Kufar ads: {len(ads)}")
    for ad in ads[:3]:
        print(f"  {ad}")