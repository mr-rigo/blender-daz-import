import cv2
import os
import argparse

def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("file", type=str, help="Name of input file.")
    parser.add_argument("newfile", type=str, help="Name of output file.")
    parser.add_argument("steps", type=int, help="Number of steps")
    parser.add_argument("--overwrite", "-o", dest="overwrite", action="store_true")
    args = parser.parse_args()

    if args.steps == 0:
        return
    if args.steps < 0 or args.steps > 8:
        print("Steps must be an integer between 1 and 8")
        return
    else:
        factor = 0.5**args.steps

    if args.overwrite:
        newfile = args.file
    else:
        fname,ext = os.path.splitext(args.file)
        if fname[-5:-1] == "-res" and fname[-1].isdigit():
            args.file = "%s%s" % (fname[:-5], ext)
        elif (fname[-10:-6] == "-res" and
              fname[-6].isdigit() and
              fname[-5] == "_" and
              fname[-4:].isdigit()):
            args.file = "%s%s%s" % (fname[:-10], fname[-5:], ext)

    if not os.path.isfile(args.file):
        print("The file %s does not exist" % args.file)
        return
    if os.path.isfile(args.newfile) and not args.overwrite:
        print("%s already exists" % os.path.basename(args.newfile))
        return

    img = cv2.imread(args.file, cv2.IMREAD_UNCHANGED)
    rows,cols = img.shape[0:2]
    newrows = max(4, int(factor*rows))
    newcols = max(4, int(factor*cols))
    newimg = cv2.resize(img, (newcols,newrows), interpolation=cv2.INTER_AREA)
    if len(newimg.shape) >= 3 and newimg.shape[2] >= 3:
        blue = newimg[:,:,0]
        green = newimg[:,:,1]
        red = newimg[:,:,2]
        if (blue == green).all() and (blue == red).all():
            print("Greyscale", args.file)
            newimg = cv2.cvtColor(newimg, cv2.COLOR_BGR2GRAY)
    print("%s: (%d, %d) => (%d %d)" % (os.path.basename(args.newfile), rows, cols, newrows, newcols))
    cv2.imwrite(os.path.join(args.file, args.newfile), newimg)

main()
