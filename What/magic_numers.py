    with open (from_folder+"/"+i, "rb") as myfile:
        header=myfile.read(24)
        header = str(binascii.hexlify(header))[2:-1]
# 4740001b0000b00d0001c100000001efff3690e23dffffff