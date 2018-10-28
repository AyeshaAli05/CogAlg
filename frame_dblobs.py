# import cv2
# import argparse
from scipy import misc
from time import time
from collections import deque

'''   
    frame() is my core algorithm of levels 1 + 2, modified for 2D: segmentation of image into blobs, then search within and between blobs.
    frame_blobs() is frame() limited to definition of initial blobs per each of 4 derivatives, vs. per 2 gradients in current frame().
    frame_dblobs() is updated version of frame_blobs with only one blob type: dblob, to ease debugging, currently in progress.
    
    Each performs several levels (Le) of encoding, incremental per scan line defined by vertical coordinate y, outlined below.
    value of y per Le line is shown relative to y of current input line, incremented by top-down scan of input image,

    1Le, line y:    x_comp(p_): lateral pixel comparison -> tuple of derivatives ders ) array ders_
    2Le, line y- 1: y_comp(ders_): vertical pixel comp -> 2D tuple ders2 ) array ders2_ 
    3Le, line y- 1+ rng*2: form_P(ders2) -> 1D pattern P) hP  
    4Le, line y- 2+ rng*2: scan_P_(P, hP) -> hP, roots: down-connections, fork_: up-connections between Ps 
    5Le, line y- 3+ rng*2: form_segment: merge vertically-connected _Ps in non-forking blob segments
    6Le, line y- 4+ rng*2+ segment depth: form_blob: merge connected segments into blobs
    
    These functions are tested through form_P, I am currently debugging scan_P_. 
    All 2D functions (y_comp, scan_P_, etc.) input two lines: higher and lower, convert elements of lower line 
    into elements of new higher line, and displace elements of old higher line into higher function.
    Higher-line elements include additional variables, derived while they were lower-line elements.
    
    Pixel comparison in 2D forms lateral and vertical derivatives: 2 matches and 2 differences per pixel. 
    They are formed on the same level because average lateral match ~ average vertical match.
    Each vertical and horizontal derivative forms separate blobs, suppressing overlapping orthogonal representations.
    They can also be summed to estimate diagonal or hypot derivatives, for blob orientation to maximize primary derivatives.
    Orientation increases primary dimension of blob to maximize match, and decreases secondary dimension to maximize difference.
    
    Subsequent union of lateral and vertical patterns is by strength only, orthogonal sign is not commeasurable?
    prefix '_' denotes higher-line variable or pattern, vs. same-type lower-line variable or pattern,
    postfix '_' denotes array name, vs. same-name elements of that array:
'''

def lateral_comp(pixel_):  # comparison over x coordinate: between min_rng of consecutive pixels within each line

    ders1_ = []  # tuples of complete 1D derivatives: summation range = rng
    rng_ders1_ = deque(maxlen=rng)  # array of ders1 within rng from input pixel: summation range < rng
    max_index = rng - 1  # max index of rng_ders1_
    pri_d, pri_m = 0, 0  # fuzzy derivatives in prior completed tuple

    for p in pixel_:  # pixel p is compared to rng of prior pixels within horizontal line, summing d and m per prior pixel
        for index, (pri_p, d, m) in enumerate(rng_ders1_):

            d += p - pri_p  # fuzzy d: running sum of differences between pixel and all subsequent pixels within rng
            m += min(p, pri_p)  # fuzzy m: running sum of matches between pixel and all subsequent pixels within rng

            if index < max_index:
                rng_ders1_[index] = (pri_p, d, m)
            else:
                ders1_.append((pri_p, d + pri_d, m + pri_m))  # completed bilateral tuple is transferred from rng_ders_ to ders_
                pri_d = d; pri_m = m  # to complement derivatives of next rng_t_: derived from next rng of pixels

        rng_ders1_.appendleft((p, 0, 0))  # new tuple with initialized d and m, maxlen displaces completed tuple from rng_t_

    ders1_ += reversed(rng_ders1_)  # or tuples of last rng (incomplete, in reverse order) are discarded?
    return ders1_


def vertical_comp(ders1_, ders2__, _dP_, dframe):
    # comparison between rng vertically consecutive pixels, forming ders2: tuple of 2D derivatives per pixel

    dP = 0, 0, 0, 0, 0, 0, 0, []  # lateral difference pattern = pri_s, L, I, D, Dy, V, Vy, ders2_
    dP_ = deque()  # line y - 1+ rng*2
    dbuff_ = deque()  # line y- 2+ rng*2: _Ps buffered by previous run of scan_P_
    new_ders2__ = deque()  # 2D: line of ders2_s buffered for next-line comp

    x = 0  # lateral coordinate of current pixel
    max_index = rng - 1  # max ders2_ index
    min_coord = rng * 2 - 1  # min x and y for form_P input: ders2 from comp over rng*2 (bidirectional: before and after pixel p)
    dy, my = 0, 0  # for initial rng of lines, to reload _dy, _vy = 0, 0 in higher tuple

    for (p, d, m), (ders2_, _dy, _my) in zip(ders1_, ders2__):  # pixel comp to rng _pixels in ders2_, summing dy and my per _pixel
        x += 1
        index = 0
        for (_p, _d, dy, _m, my) in ders2_:  # vertical derivatives are incomplete; prefix '_' denotes higher-line variable

            dy += p - _p  # fuzzy dy: running sum of differences between pixel and all lower pixels within rng
            my += min(p, _p)  # fuzzy my: running sum of matches between pixel and all lower pixels within rng

            if index < max_index:
                ders2_[index] = (_p, d, dy, m, my)

            elif x > min_coord and y > min_coord + ini_y:

                _v = _m - abs(d) - ave  # projected m is cancelled by negative d: d/2, + rdn value of overlapping dP: d/2?
                vy = my + _my - abs(dy) - ave
                ders2 = _p, _d, dy + _dy, _v, vy
                dP, dP_, dbuff_, _dP_, dframe = form_P(ders2, x, dP, dP_, dbuff_, _dP_, dframe)

            index += 1

        ders2_.appendleft((p, d, 0, m, 0))  # initial dy and my = 0, new ders2 replaces completed t2 in vertical ders2_ via maxlen
        new_ders2__.append((ders2_, dy, my))  # vertically-incomplete 2D array of tuples, converted to ders2__, for next-line ycomp

    if y > min_coord + ini_y:  # not-terminated P at the end of each line is buffered or scanned:

        if y == rng * 2 + ini_y:  # _P_ initialization by first line of Ps, empty until vertical_comp returns P_
            dP_.append([dP, x, 0, []])  # empty _fork_ in the first line of hPs, x-1: delayed P displacement
        else:
            dP_, dbuff_, _dP_, dframe = scan_P_(x, dP, dP_, dbuff_, _dP_, dframe)  # scans higher-line Ps for contiguity

    return new_ders2__, dP_, dframe  # extended in scan_P_; net_s are packed into frames


def form_P(ders, x, P, P_, buff_, hP_, frame):  # initializes, accumulates, and terminates 1D pattern: dP | vP | dyP | vyP

    p, d, dy, v, vy = ders  # 2D tuple of derivatives per pixel, "y" denotes vertical vs. lateral derivatives
    s = 1 if d > 0 else 0  # core = 0 is negative: no selection?

    if s == P[0] or x == rng * 2:  # s == pri_s or initialized: P is continued, else terminated:
        pri_s, L, I, D, Dy, V, Vy, ders_ = P
    else:
        if y == rng * 2 + ini_y:  # _P_ initialization by first line of Ps, empty until vertical_comp returns P_
            P_.append([P, x-1, 0, []])  # first line of hPs: container to maintain fork refs
        else:
            P_, buff_, hP_, frame = scan_P_(x-1, P, P_, buff_, hP_, frame)  # scans higher-line Ps for contiguity
            # x-1: ends with prior p
        L, I, D, Dy, V, Vy, ders_ = 0, 0, 0, 0, 0, 0, []  # new P initialization

    L += 1  # length of a pattern, continued or initialized input and derivatives are accumulated:
    I += p  # summed input
    D += d  # lateral D
    Dy += dy  # vertical D
    V += v  # lateral V
    Vy += vy  # vertical V
    ders_.append(ders)  # ders2s are buffered for oriented rescan and incremental range | derivation comp

    P = s, L, I, D, Dy, V, Vy, ders_
    return P, P_, buff_, hP_, frame  # accumulated within line, P_ is a buffer for conversion to _P_


def scan_P_(x, P, P_, _buff_, hP_, frame):  # P scans shared-x-coordinate hPs in hP_, forms overlaps

    buff_ = deque()  # new buffer for displaced hPs, for scan_P_(next P)
    fork_ = []  # hPs connected to input P
    ini_x = 0  # always starts while, next ini_x = _x + 1

    while ini_x <= x:  # while x values overlap between P and hP
        if _buff_:
            hP = _buff_.popleft()  # load hP buffered in prior run of scan_P_, if any
            _P, _x, roots, _fork_ = hP  # stable container for ref by lower-line forks
        elif hP_:
            hP = hP_.popleft()
            _P, _x, roots, _fork_ = hP  # roots = 0: number of Ps connected to _P, each: pri_s, L, I, D, Dy, V, Vy, ders_
        else:
            break  # higher line ends, all hPs converted to seg

        if P[0] == _P[0]:  # if s == _s: core sign match, + selective inclusion if contiguity eval?
            roots += 1; hP[2] = roots  # nothing else is modified
            fork_.append(hP)  # P-connected hPs

        if _x > x:  # x overlap between hP and next P: hP is buffered for next scan_P_, else hP included in blob segment
            buff_.append(hP)
        else:
            ave_x = _x - (_P[1]-1) // 2  # average x of _P; _P[1]-1: extra-x L = L-1 (1x in L)
            ini = 1
            if y > rng * 2 + 1 + ini_y:  # beyond 1st line of _fork_ Ps, else: blob segment ini only
                if len(_fork_) == 1 and _fork_[0][5] == 1:  # roots
                    # _fork_[0] blob segment [Vars, Py_, x, Dx, blob, roots, fork_] is incremented with _P:
                    s, L, I, D, Dy, V, Vy, ders_ = _P
                    _fork_[0][0][0] += L  # seg[0]: Vars
                    _fork_[0][0][1] += I
                    _fork_[0][0][2] += D
                    _fork_[0][0][3] += Dy
                    _fork_[0][0][4] += V
                    _fork_[0][0][5] += Vy
                    if y > rng * 2 + 2 + ini_y:
                        dx = ave_x - fork_[0][2]
                    else: dx = 0
                    _fork_[0][1].append((_P, dx))  # seg[1]: Py_
                    _fork_[0][2] = ave_x
                    _fork_[0][3] += dx  # Dx for seg norm and orient eval, | += |xd| for curved yL? # blob, roots, fork_ are not modified

                    hP = _fork_[0]  # passed to form_blob, but not returned?
                    ini = 0

            if ini == 1:
                del hP[:]; hP += list(_P[1:7]), [(_P, 0)], ave_x, 0, [_P[0],0,0,0,0,0,0,0,y,[]], roots, _fork_
                # segment [Vars, Py_, ave_x, Dx, blob, roots, _fork_] is initialized at hP, replacing its fork_ refs

            if roots == 0:  # bottom segment is terminated and added to blob at _fork_[0][4], initialized above for same form_blob
                frame = form_blob(hP, frame)  # del(hP[:]); hP += seg or update by side effect: test roots forks at blob_x?

        ini_x = _x + 1  # first x of next hP

    buff_ += _buff_  # _buff_ is likely empty
    P_.append([P, x, 0, fork_])  # P with no overlap to next _P is buffered for next-line scan_P_, converted to hP

    return P_, buff_, hP_, frame  # hP_ and buff_ contain only remaining _Ps, with _x => next x


def form_blob(term_seg, frame):  # continued or initialized blob (connected segments) is incremented by terminated segment

    [L, I, D, Dy, V, Vy], Py_, x, xD, blob, roots, fork_ = term_seg
    if fork_:
        iseg = fork_.pop[0]  # blob -> fork_[0] only, ref by other forks, no return by index, seg in enumerate(fork_):
        iseg[4][1] += L  # initial seg[4] = _blob
        iseg[4][2] += I
        iseg[4][3] += D
        iseg[4][4] += Dy
        iseg[4][5] += V
        iseg[4][6] += Vy
        iseg[4][7] += xD
        iseg[4][8] = max(len(Py_), iseg[4][8])  # blob yD += max root seg Py_:  if y - len(Py_) +1 < min_y?
        iseg[4][9].append([[L, I, D, Dy, V, Vy], Py_, x, xD], blob)  # term_seg is appended to fork[0] _root_

        iseg[5] -= 1  # roots -= 1, because root segment was terminated
        if iseg[5] == 0:  # recursive higher-level segment-> blob inclusion and termination test
            frame = form_blob(iseg, frame)  # no return: del (seg[:]); seg += iseg; fork_[index] = seg: ref from blob only?

        for seg in fork_:
            seg[4] = iseg[4]  # ref to unique blob, for each root? fork_-> root_ mapping vs. separate seg[4][9].append?
            seg[5] -= 1
            if seg[5] == 0:  # seg roots; recursive higher-level segment -> blob inclusion and termination test
                frame = form_blob(seg, frame)  # no return: del (seg[:]); seg += iseg; fork_[index] = seg: ref from blob only?

    # co_roots += co_fork, term subb (sub_blob ! blob) while binary co_root | co_fork count?
    # right_count and left_1st (for transfer at roots+forks term)
    # right: cont roots and len(_fork_), each summed at current subb term, for blob term eval?

    else:  # fork_ == 0: blob is terminated and added to frame:
        s, L, I, D, Dy, V, Vy, xD, yD, root_ = blob
        frame[0] += L  # frame [Vars, blob_]; Vars to compute averages, redundant for same-scope alt_frames
        frame[1] += I
        frame[2] += D
        frame[3] += Dy
        frame[4] += V
        frame[5] += Vy
        frame[6] += xD  # for frame orient eval, += |xd| for curved max_L?
        frame[7] += yD
        frame[8].append(((s, L, I, D, Dy, V, Vy, x - xD//2, xD, y, yD), root_))  # blob_; xD for blob orient eval before comp_P

    return frame  # or no return needed?  no return term_seg[5] = fork_: no roots to ref


def image_to_blobs(image):  # postfix '_' denotes array vs. element, prefix '_' denotes higher-line vs. lower-line variable

    _P_ = deque()  # higher-line same- d-, v-, dy-, vy- sign 1D patterns
    frame = [0, 0, 0, 0, 0, 0, 0, 0, []]  # L, I, D, Dy, V, Vy, xD, yD, blob_
    global y
    y = ini_y  # initial input line, set at 400 as that area in test image seems to be the most diverse

    ders2_ = deque(maxlen=rng)  # vertical buffer of incomplete derivatives tuples, for fuzzy ycomp
    ders2__ = []  # horizontal line of vertical buffers: 2D array of 2D tuples, deque for speed?
    pixel_ = image[ini_y, :]  # first line of pixels at y == 0
    ders1_ = lateral_comp(pixel_)  # after part_comp (pop, no t_.append) while x < rng?

    for (p, d, m) in ders1_:
        ders2 = p, d, 0, m, 0  # dy, my initialized at 0
        ders2_.append(ders2)  # only one tuple per first-line ders2_
        ders2__.append((ders2_, 0, 0))  # _dy, _my initialized at 0

    for y in range(ini_y + 1, Y):  # or Y-1: default term_blob in scan_P_ at y = Y?

        pixel_ = image[y, :]  # vertical coordinate y is index of new line p_
        ders1_ = lateral_comp(pixel_)  # lateral pixel comparison
        ders2__, _P_, frame = vertical_comp(ders1_, ders2__, _P_, frame)  # vertical pixel comparison

    # frame ends, last vertical rng of incomplete ders2__ is discarded,
    # vertically incomplete P_ patterns are still inputted in scan_P_?
    return frame  # frame of 2D patterns to be outputted to level 2


# pattern filters: eventually updated by higher-level feedback, initialized here as constants:

rng = 2  # number of leftward or upward pixels compared to each input pixel
ave = 63 * rng * 2  # average match: value pattern filter
ave_rate = 0.25  # average match rate: ave_match_between_ds / ave_match_between_ps, init at 1/4: I / M (~2) * I / D (~2)
ini_y = 400

image = misc.face(gray=True)  # read image as 2d-array of pixels (gray scale):
image = image.astype(int)
Y, X = image.shape  # image height and width

# or:
# argument_parser = argparse.ArgumentParser()
# argument_parser.add_argument('-i', '--image', help='path to image file', default='./images/raccoon.jpg')
# arguments = vars(argument_parser.parse_args())
# image = cv2.imread(arguments['image'], 0).astype(int)

start_time = time()
frame_of_blobs = image_to_blobs(image)
end_time = time() - start_time
print(end_time)

