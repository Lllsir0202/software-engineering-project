import csv
import sys
sys.path.append('../')
from app import app
from database.models import db, FishProfile

def import_fish(csv_path):
    count = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            fish = FishProfile(
                species=row["Species"],
                weight=float(row["Weight(g)"]),
                length1=float(row["Length1(cm)"]),
                length2=float(row["Length2(cm)"]),
                length3=float(row["Length3(cm)"]),
                height=float(row["Height(cm)"]),
                width=float(row["Width(cm)"]),
            )
            db.session.add(fish)
            count += 1
    db.session.commit()
    print(f"成功导入 {count} 条鱼类数据")

if __name__ == "__main__":
    with app.app_context():
        import_fish("../data/Fish.csv")