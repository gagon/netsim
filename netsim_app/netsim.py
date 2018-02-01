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


def calculate_network():

    gap=read_gap_file()
    pipe_list=list(gap["pipes"].keys())
    well_list=list(gap["wells"].keys())
    joint_list=list(gap["joints"].keys())
    sep_list=list(gap["seps"].keys())

    sep_list_parent=[]
    for sep in sep_list:
        from_item=sep
        from_item_type="sep"
        to_item=""
        to_item_type=""

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
            for p in pipe_list:
                if gap["pipes"][p]["masked"]==0:
                    if gap["pipes"][p]["to"]==parent["from_item"]:

                        from_item=gap["pipes"][p]["from"]
                        from_item_type=get_type(gap,from_item)
                        to_item=gap["pipes"][p]["to"]
                        to_item_type=get_type(gap,to_item)

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

                    tol+=abs(gap["wells"][from_item]["results"]["fwhp"]-pres_out-dp) # point of checking if convergence is reached
                elif from_item_type=="joints":
                    gap["joints"][from_item]["results"]["pres"]=pres_out


        for item1,val1 in gap.items():
            if item1=="seps" or item1=="joints":
                for item2,val2 in val1.items():
                    # print(item2,val2)
                    gap[item1][item2]["results"]["qoil"]=0.0
                    gap[item1][item2]["results"]["qgas"]=0.0
                    gap[item1][item2]["results"]["qwat"]=0.0



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


            gap["wells"][well]["results"]["dp"]=dp
            if well=="9815":
                print(well,fwhp_min,fwhp,dp,iters)
            # print(well,dp,iters)
        iters+=1

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
