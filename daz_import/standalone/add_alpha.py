import cv2
import os
import argparse

def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("opaque", type=str, help="Opaque pattern")
    parser.add_argument("alpha", type=str, help="Alpha pattern")
    args = parser.parse_args()

    folder = os.path.dirname("__file__")
    alphafiles = []
    opaquefiles = []
    for file in os.listdir():
        if args.opaque in file:
            opaquefiles.append(file)
        if args.alpha in file:
            alphafiles.append(file)

    for ofile in opaquefiles:
        afile = ofile.replace(args.opaque, args.alpha)
        if afile in alphafiles:
            opath = os.path.join(folder, ofile)
            apath = os.path.join(folder, afile)
            # Read RGB and alpha files
            oimg = cv2.imread(opath, cv2.IMREAD_UNCHANGED)
            aimg = cv2.imread(apath, cv2.IMREAD_UNCHANGED)
            if aimg.shape[2] >= 3:
                aimg = cv2.cvtColor(aimg, cv2.COLOR_BGR2GRAY)
            # Resize alpha file if necessary
            orows,ocols = oimg.shape[0:2]
            arows,acols = aimg.shape[0:2]
            if orows != arows or ocols != acols:
                aimg = cv2.resize(aimg, (orows,ocols), interpolation=cv2.INTER_AREA)
            # Create RGBA file
            nimg = cv2.cvtColor(oimg, cv2.COLOR_RGB2RGBA)
            nimg[:,:,3] = aimg
            # Save RGBA file
            nfile = os.path.splitext(ofile)[0] + ".png"
            print("%s + %s => %s" % (ofile, afile, nfile))
            npath = os.path.join(folder, nfile)
            cv2.imwrite(npath, nimg)


main()
print("Done")
