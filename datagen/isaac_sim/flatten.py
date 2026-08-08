from pxr import Usd
s = Usd.Stage.Open("/root/barrel/pile.usd")
s.Flatten().Export("/root/barrel/pile_flat.usd")
print("flattened OK")
