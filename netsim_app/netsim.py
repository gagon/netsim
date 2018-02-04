import json
import numpy as np
import os
import dpath.util as dpu
import datetime

def read_gap_file():
    dirname, filename = os.path.split(os.path.abspath(__file__))
    fullpath=os.path.join(dirname,'temp\gap.json')
    gap = json.load(open(fullpath))
    return gap

def save_gap_file(gap):
    dirname, filename = os.path.split(os.path.abspath(__file__))
    fullpath=os.path.join(dirname,'temp\gap.json')
    json.dump(gap, open(fullpath, 'w'),indent=4, sort_keys=True)
    return None

def calculate_pres_drop(pipe,pres_in,qtot):

    dp=(0.001*qtot*pipe["corr"]["a"]+pipe["corr"]["b"])*pipe["lenght"]/100.0
    pres_out=pres_in+dp
    return pres_out

def get_type(gap,uid):
    pipe_list=list(gap["pipes"].keys())
    well_list=list(gap["wells"].keys())
    joint_list=list(gap["joints"].keys())
    sep_list=list(gap["seps"].keys())
    if uid in pipe_list:
        return "pipes"
    elif uid in well_list:
        return "wells"
    elif uid in joint_list:
        return "joints"
    elif uid in sep_list:
        return "seps"

def clear_results(gap):
    for item,v in gap["wells"].items():
        # gap["wells"][item]["results"]["dp"]=0.0 # removed as dp from prev solve is needed for optimization algorithm
        gap["wells"][item]["results"]["fwhp"]=0.0
        gap["wells"][item]["results"]["pres"]=0.0
        gap["wells"][item]["results"]["qgas"]=0.0
        gap["wells"][item]["results"]["qoil"]=0.0
        gap["wells"][item]["results"]["qwat"]=0.0
    for item,v in gap["seps"].items():
        gap["seps"][item]["results"]["qgas"]=0.0
        gap["seps"][item]["results"]["qoil"]=0.0
        gap["seps"][item]["results"]["qwat"]=0.0
    for item,v in gap["joints"].items():
        gap["joints"][item]["results"]["pres"]=0.0
        gap["joints"][item]["results"]["qgas"]=0.0
        gap["joints"][item]["results"]["qoil"]=0.0
        gap["joints"][item]["results"]["qwat"]=0.0
    for item,v in gap["pipes"].items():
        gap["pipes"][item]["results"]["dp"]=0.0
        gap["pipes"][item]["results"]["pres"]=0.0
        gap["pipes"][item]["results"]["qgas"]=0.0
        gap["pipes"][item]["results"]["qoil"]=0.0
        gap["pipes"][item]["results"]["qwat"]=0.0
    return gap


def build_network():

    gap=read_gap_file()
    gap=clear_results(gap)
    pipe_list=sorted(list(gap["pipes"].keys()))
    well_list=sorted(list(gap["wells"].keys()))
    joint_list=sorted(list(gap["joints"].keys()))
    sep_list=sorted(list(gap["seps"].keys()))

    seps=[]
    for sep in sep_list: # highest level of network elements
        from_item=sep
        from_item_type="seps"
        to_item=""
        to_item_type=""

        sep_list_parent=[]
        sep_list_parent.append({
            "from_item":from_item,
            "to_item":to_item,
            "pipe":"",
            "from_item_type":from_item_type,
            "to_item_type":to_item_type
        })

        parents=sep_list_parent

        levels=[]
        flag=1
        while flag:
            children=[]
            for parent in parents:

                # continue build network
                for p in pipe_list:
                    print(parent["from_item"])
                    if gap["pipes"][p]["masked"]==0: # check if pipe is masked
                        if gap["pipes"][p]["to"]==parent["from_item"]:

                            from_item=gap["pipes"][p]["from"]
                            from_item_type=get_type(gap,from_item)
                            to_item=gap["pipes"][p]["to"]
                            to_item_type=get_type(gap,to_item)

                            from_maskflag=0
                            if "masked" in gap[from_item_type][from_item]:
                                if gap[from_item_type][from_item]["masked"]==1:
                                    from_maskflag=1

                            if from_maskflag==0:
                                children.append({
                                    "from_item":from_item,
                                    "to_item":to_item,
                                    "pipe":p,
                                    "from_item_type":from_item_type,
                                    "to_item_type":to_item_type
                                })

            if children:
                levels.append(children)
                parents=children
                flag=1
            else:
                flag=0

        seps.append(levels)

    gap["network"]=seps
    save_gap_file(gap)

    return gap

def calculate_network():
    gap=read_gap_file()
    gap=clear_results(gap)
    seps=gap["network"]

    for sep in seps: # highest level of network elements
        if sep:
            levels=sep

            iters=0
            tol=1.0 # init value to pass condition
            while tol>0.9 and iters<10:

                tol=0.0
                for level in levels:

                    for l in level:

                        to_item=l["to_item"]
                        to_item_type=l["to_item_type"]
                        from_item=l["from_item"]
                        from_item_type=l["from_item_type"]


                        if to_item_type=="seps":
                            pres_in=gap["seps"][to_item]["pres"]
                        elif to_item_type=="joints":
                            pres_in=gap["joints"][to_item]["results"]["pres"]
                        qgas=gap[from_item_type][from_item]["results"]["qgas"]
                        qoil=gap[from_item_type][from_item]["results"]["qoil"]
                        qwat=gap[from_item_type][from_item]["results"]["qwat"]
                        qtot=qgas*5.0+qoil+qwat


                        pres_out=calculate_pres_drop(gap["pipes"][l["pipe"]],pres_in,qtot)

                        gap["pipes"][l["pipe"]]["results"]["pres"]=pres_in
                        gap["pipes"][l["pipe"]]["results"]["dp"]=pres_out-pres_in
                        gap["pipes"][l["pipe"]]["results"]["qgas"]=qgas
                        gap["pipes"][l["pipe"]]["results"]["qoil"]=qoil
                        gap["pipes"][l["pipe"]]["results"]["qwat"]=qwat

                        if from_item_type=="wells":

                            dp=gap["wells"][from_item]["results"]["dp"]
                            gap["wells"][from_item]["results"]["pres"]=pres_out
                            gap["wells"][from_item]["results"]["fwhp"]=pres_out+dp
                            gap["wells"][from_item]["results"]["qoil"]=\
                                np.interp(gap["wells"][from_item]["results"]["fwhp"],\
                                            gap["wells"][from_item]["pc"]["fwhps"],gap["wells"][from_item]["pc"]["qoil"])
                            gap["wells"][from_item]["results"]["qgas"]=gap["wells"][from_item]["results"]["qoil"]*gap["wells"][from_item]["gor"]/1000.0
                            gap["wells"][from_item]["results"]["qwat"]=gap["wells"][from_item]["results"]["qoil"]*\
                                                                        gap["wells"][from_item]["wct"]/100.0/(1.0-gap["wells"][from_item]["wct"]/100.0)
                            # print(gap["wells"][from_item]["results"]["fwhp"],pres_out,dp)
                            if iters==0:
                                tol+=1.0
                            else:
                                tol+=abs(gap["wells"][from_item]["results"]["fwhp"]-pres_out-dp) # point of checking if convergence is reached
                        elif from_item_type=="joints":
                            gap["joints"][from_item]["results"]["pres"]=pres_out


                for level in levels: # init rates for calculating aggregates
                    for l in level:
                        if l["to_item_type"]=="joints":
                            to_item=l["to_item"]
                            gap[to_item_type][to_item]["results"]["qgas"]=0.0
                            gap[to_item_type][to_item]["results"]["qoil"]=0.0
                            gap[to_item_type][to_item]["results"]["qwat"]=0.0



                for level in levels[::-1]:

                    for l in level:
                        to_item=l["to_item"]
                        to_item_type=l["to_item_type"]
                        from_item=l["from_item"]
                        from_item_type=l["from_item_type"]

                        qgas_in=gap[from_item_type][from_item]["results"]["qgas"]
                        qoil_in=gap[from_item_type][from_item]["results"]["qoil"]
                        qwat_in=gap[from_item_type][from_item]["results"]["qwat"]

                        gap[to_item_type][to_item]["results"]["qgas"]+=qgas_in
                        gap[to_item_type][to_item]["results"]["qoil"]+=qoil_in
                        gap[to_item_type][to_item]["results"]["qwat"]+=qwat_in

                iters+=1

    save_gap_file(gap)
    return gap

def optimize_network():
    start_time=datetime.datetime.now()
    gap=read_gap_file()
    wells=sorted(list(gap["wells"].keys()))

    iters=0
    tol=1.0
    while tol>0.01 and iters<10:
        tol=0.0
        for well in wells:
            if gap["wells"][well]["masked"]==0:
                fwhp_min=gap["wells"][well]["constraints"]["fwhp_min"]
                fwhp=gap["wells"][well]["results"]["fwhp"]
                pres=gap["wells"][well]["results"]["pres"] # flowline pressure (choke downstream pressure)
                dp=gap["wells"][well]["results"]["dp"]
                # if well=="9815":
                #     print("===")
                #     print(well,fwhp_min,fwhp,dp,iters)


                if iters==0:
                    dp=0.0
                    tol+=1.0
                elif fwhp_min>pres:
                    dp=fwhp_min-pres
                    tol+=dp
                print(well,fwhp_min,pres,dp)


                gap["wells"][well]["results"]["dp"]=dp
                # if well=="9815":
                #     print(well,fwhp_min,fwhp,dp,iters)
                # print(well,dp,iters)
        iters+=1
        print(iters,tol)

        save_gap_file(gap)

        gap=calculate_network()

    end_time=datetime.datetime.now()
    return gap,end_time-start_time

def DoGet(dictionary, path):
    val=dpu.get(dictionary, path)
    return val

def DoSet(dictionary, path, val):
    orig_val=DoGet(dictionary, path)
    if isinstance(orig_val, int):
        val=int(val)
    elif isinstance(orig_val, float):
        val=float(val)

    dpu.set(dictionary, path, val)
    save_gap_file(dictionary)
    return dictionary

def DoGetAll(dictionary, path):
    vals=list(dpu.search(dictionary, path, yielded=True))
    return vals


def DoSetAll(dictionary, path, param, vals):
    path+="/**/"+param
    orig_vals=DoGetAll(dictionary, path)
    orig_vals=sorted(orig_vals,key=lambda x:x[0])

    if len(orig_vals)==len(vals):
        for i,v in enumerate(orig_vals):
            g=DoSet(dictionary,v[0],vals[i])
    else:
        print("Vals array is not same size as target params array")

    return dictionary


if __name__=="__main__":

    gap=read_gap_file()

    gap=DoSet(gap,"pipes/p_9815_tl1/masked",0)
    gap=DoSet(gap,"pipes/p_9815_tl2/masked",1)

    gap=calculate_network()
    print(gap["seps"]["kpc"]["results"]["qgas"])

    gap=DoSet(gap,"pipes/p_9815_tl1/masked",1)
    gap=DoSet(gap,"pipes/p_9815_tl2/masked",0)

    gap=calculate_network(gap)
    print(gap["seps"]["kpc"]["results"]["qgas"])
















    print("")
