#!/usr/bin/python3

"""
Last update: March 2021
Author: Luigi D'Ascenzo, PhD - The Scripps Research Institute, La Jolla (CA)
Contact info: dascenzoluigi@gmail.com
GitHub project repository: https://github.com/ldascenzo/pytheas

***DESCRIPTION***
Final step of the Pytheas in silico digest library generation. m/z values for precursor ions and all the derived
CID fragment ions are added to each target and decoy sequences. Isotopic labeling can be added via an additional
nucleotides dictionary file. Charge tables for precursor ions and fragment ions (if different from the default) can
also be provided.
More information on the elemental masses, CID fragmentation of RNA and the available options/parameters can be found
in the Digest section of Pytheas manual.

***OPTIONS***
--ion_mode (REQUIRED): Select positive (+) or negative (-) ion mode
--nts_light (REQUIRED): Excel spreadsheet with the standard nucleotides and optional modification alphabet.
--nts_heavy (OPTIONAL): Excel spreadsheet with the isotopically labeled nucleotides and optional modification
                                 alphabet.
--MS1_charges (OPTIONAL, default = charges_MS1.txt): charge table file for precursor ions (MS1)
--MS2_charges (OPTIONAL, default = charges_MS2.txt): charge table file for fragment ions (MS2)
--MS1_mzlow (OPTIONAL, default = 400): minimum m/z for ions in the MS1 output file
--MS1_mzhigh (OPTIONAL, default = 2000): maximum m/z for ions in the MS1 output file
--MS2_mzlow (OPTIONAL, default = 300): minimum m/z for ions in the MS2 output file
--MS2_mzhigh (OPTIONAL, default = 2000): maximum m/z for ions in the MS2 output file
--CID_series (OPTIONAL, default = c y a a-B w b x d z y-P z-P): list of CID fragments for the generation of
                                                                sequence-defining ions in the MS2 output file
--mz_consolidation (OPTIONAL, default = n): Check (y/n) if occurrences of nucleotides within a specified ppm
                                            threshold have to be consolidated as 'X' in the final output
--MS1_ppm_consolidation (OPTIONAL, default = 0): ppm threshold at MS1 level to check whether two bases from
                                                 the alphabet file have to be consolidated since indistinguishable
                                                 in the MS1_ppm window used for matching
--MS2_ppm_consolidation (OPTIONAL, default = 0): ppm threshold at MS2 level to check whether two bases from the
                                                 alphabet file have to be consolidated since indistinguishable
                                                 in the MS2_ppm window used for matching

***OUTPUT***
1) Digest_MS2.txt (or MS1 if requested) -> in silico digest library file ready to be used for matching, with all
                 the info on each precursor ion and its derived fragmentation ions

"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
from shutil import move

import consolidate_tools as ct

##########
# ELEMENT MASS DICTIONARY
##########
"""
Masses from:
(1) http://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl?ele=&ascii=html&isotype=some
(2) http://www.sisweb.com/referenc/source/exactmaa.htm

Note that for each element with no specified isotope the mass of the most abundant isotope is used. 
In the case of O, C, H and N the most abundant isotope is >=99% abundant. 
S32 has 95% abundance
Se80 has only 49% abundance, so you could consider adding multiple isotopes if working with Se 
Se80 has only 49% abundance, so you could consider adding multiple isotopes if working with Se 
"""
ele_mass = {
    "C": 12.0000000,
    "H": 1.007825032,
    "N": 14.0030740044,
    "O": 15.9949146196,
    "S": 31.9720711744,
    "P": 30.9737619984,
    "Se": 79.9165218,
    "F": 18.998403163,
    "H2": 2.0141017781,
    "C13": 13.0033548351,
    "N15": 15.0001088989,
    "O18": 17.9991596128,
}

# Initialize and define launch options
parser = argparse.ArgumentParser()

parser.add_argument(
    "--ion_mode",
    choices=["+", "-"],
    required=True,
    help="Choose positive (+) or negative (-) ion mode",
)
parser.add_argument(
    "--nts_light",
    required=True,
    help="Custom file with nucleotides and modification alphabet (Required)",
)
parser.add_argument(
    "--nts_heavy",
    default=None,
    help="Custom file with nucleotides and modification alphabet and isotopic labeling info (Optional)",
)
parser.add_argument(
    "--MS1_charges",
    default="charges_MS1.txt",
    help="Charge table file for MS1 ions, located in the same directory of the script "
    "(Required, default = charges_MS1.txt) ",
)
parser.add_argument(
    "--MS2_charges",
    default="charges_MS2.txt",
    help="Charge table file for MS2 ions, located in the same directory of the script "
    "(Required, default = charges_MS2.txt) ",
)
parser.add_argument(
    "--MS1_mzlow",
    default=400,
    type=int,
    help="The minimum m/z value to be output when calculating MS1 ions (Optional, default=400)",
)
parser.add_argument(
    "--MS1_mzhigh",
    default=2000,
    type=int,
    help="The maximum m/z value to be output when calculating MS1 ions (Optional, default=2000)",
)
parser.add_argument(
    "--MS2_mzlow",
    default=300,
    type=int,
    help="The minimum m/z value to be output when calculating MS2 ions (Optional, default=300)",
)
parser.add_argument(
    "--MS2_mzhigh",
    default=2000,
    type=int,
    help="The maximum m/z value to be output when calculating MS2 ions (Optional, default=2000)",
)
parser.add_argument(
    "--CID_series",
    nargs="*",
    default=["c", "y", "a", "a-B", "w", "b", "x", "d", "z", "y-P", "z-P"],
    choices=["c", "y", "a", "a-B", "w", "b", "x", "d", "z", "y-P", "z-P"],
    help="CID fragments to include when calculating MS2 ions "
    "(Required, default=c,y,a,a-B,w,b,x,d,z,y-P,z-P). "
    "Input of values spaced without '=' nor commas",
)
parser.add_argument(
    "--mz_consolidation",
    default="n",
    choices=["y", "n"],
    help="Check (y/n) if occurrences of nucleotides within a specified ppm threshold "
    "have to be consolidated as 'X' in the final output (Optional, default = n)",
)
parser.add_argument(
    "--MS1_ppm_consolidation",
    default=0,
    type=float,
    help="ppm threshold for MS1 masses to check whether two bases from the alphabet file "
    "have to be consolidated since indistinguishable in the MS1_ppm window used for matching "
    "(Optional, default = 0)",
)
parser.add_argument(
    "--MS2_ppm_consolidation",
    default=0,
    type=float,
    help="ppm threshold for MS2 masses to check whether two bases from the alphabet file "
    "have to be consolidated since indistinguishable in the MS2_ppm window used for matching "
    "(Optional, default = 0)",
)

args = parser.parse_args()


class DictDiffer(object):
    """
    Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """

    def __init__(self, current_dict, past_dict):
        self.current_dict, self.past_dict = current_dict, past_dict
        self.set_current, self.set_past = set(current_dict.keys()), set(
            past_dict.keys()
        )
        self.intersect = self.set_current.intersection(self.set_past)

    def added(self):
        return self.set_current - self.intersect

    def removed(self):
        return self.set_past - self.intersect

    def changed(self):
        return set(
            o for o in self.intersect if self.past_dict[o] != self.current_dict[o]
        )

    def unchanged(self):
        return set(
            o for o in self.intersect if self.past_dict[o] == self.current_dict[o]
        )


def __controls():
    """
    Make sure the right options with right values are assigned for the correct execution of the program
    Also check if the nucleotide dictionaries for light and heavy atoms are consistent with what used in the
    preceding steps
    """
    # Check the consistency of nucleotides alphabets between this scripts and the preceding ones for light atoms
    df_light = read_excel_input(args.nts_light)

    d = DictDiffer(read_csv(), dict(zip(df_light.ID, df_light.ID_ext)))

    if len(d.changed()) != 0:
        print(
            "WARNING! One or more nts IDs from the input nts_light have different ID_ext compared "
            "to the alphabet used in the previous scripts. List of IDs with differences: {}"
            "  Please check carefully your input dictionary and rerun the script\n".format(
                d.changed()
            )
        )

    if len(d.added()) != 0:
        print(
            "WARNING! One or more nts IDs from the input nts_light are missing compared "
            "to the alphabet used in the previous scripts. List of missing IDs: {}"
            "  Please check carefully your input dictionary and rerun the script\n".format(
                d.added()
            )
        )

    if len(d.removed()) != 0:
        print(
            "WARNING! One or more nts IDs from the input nts_light are not present "
            "in the alphabet used in the previous scripts. List of absent IDs: {}"
            "  Please check carefully your input dictionary and rerun the script\n".format(
                d.removed()
            )
        )

    if args.nts_heavy:

        # Check the consistency of nucleotides alphabets between this scripts and the preceding ones for heavy atoms
        df_heavy = read_excel_input(args.nts_heavy)

        d = DictDiffer(read_csv(), dict(zip(df_heavy.ID, df_heavy.ID_ext)))

        if len(d.changed()) != 0:
            print(
                "WARNING! One or more nts IDs from the input nts_heavy have different ID_ext compared "
                "to the alphabet used in the previous scripts. List of IDs with differences: {}"
                "  Please check carefully your input dictionary and rerun the script\n".format(
                    d.changed()
                )
            )

        if len(d.added()) != 0:
            print(
                "WARNING! One or more nts IDs from the input nts_heavy are missing compared "
                "to the alphabet used in the previous scripts. List of missing IDs: {}"
                "  Please check carefully your input dictionary and rerun the script\n".format(
                    d.added()
                )
            )

        if len(d.removed()) != 0:
            print(
                "WARNING! One or more nts IDs from the input nts_heavy are not present "
                "in the alphabet used in the previous scripts. List of absent IDs: {}"
                "  Please check carefully your input dictionary and rerun the script\n".format(
                    d.removed()
                )
            )


def ppm_range(value, difference):
    """
    Calculate incertitude on MS1/MS2 masses equivalent to given ppms
    """
    return difference * 1000000 / value


def round_masses(mass):
    """
    Round all the masses for the output to 8 digits after comma
    """
    if mass == "-":
        return "-"
    else:
        return round(mass, 8)


def read_csv(input_csv="nts_light.csv"):
    """
    Produce a dictionary nts_alphabet
    mod_alphabet contains all ID : ID_ext couples, thus the one letter and extended codes for each nucleobase
    """
    if not os.path.exists(input_csv):
        print(
            "ERROR! File {} with info on nucleotides from script 2_modify.py is missing. "
            "Execution terminated without output".format(input_csv)
        )
        sys.exit(1)

    else:
        # Read the csv file with the nucleotides dictionary
        df = pd.read_csv(input_csv, usecols=["ID", "ID_ext"])

        # Drop rows with NaN values
        df = df[pd.notnull(df["ID"])]

        return dict(zip(df.ID, df.ID_ext))


def read_excel_input(nts_file):
    """
    Generate a dataframe with all the info on the nucleotides from the input file nts_light
    """
    # Checking that the nts_light file given in argument exists
    if not os.path.exists(nts_file):
        print(
            "ERROR! File {} does not exist. Execution terminated without generating any output".format(
                nts_file
            )
        )
        sys.exit(1)

    # Create a dataframe with info from Excel spreadsheet
    df = pd.read_excel(nts_file, header=12)

    # Drop rows with NaN values
    df = df[pd.notnull(df["ID"])]

    # Transform all ID values in string (so numbers can be used as one letter code for bases)
    df = df.astype({"ID": str})

    return df


def nts_mass(df):
    """
    Create a dictionary with the masses of all nts based on their atomic composition
    """
    mass_nts, mass_base, mass_backbone = {}, {}, {}

    for index, row in df.iterrows():
        # Calculate mass of the base only
        mass_b = (
            np.float64(row["C"]) * ele_mass["C"]
            + np.float64(row["O"]) * ele_mass["O"]
            + np.float64(row["H"]) * ele_mass["H"]
            + np.float64(row["N"]) * ele_mass["N"]
            + np.float64(row["P"]) * ele_mass["P"]
            + np.float64(row["S"]) * ele_mass["S"]
            + np.float64(row["Se"]) * ele_mass["Se"]
            + np.float64(row["F"]) * ele_mass["F"]
            + np.float64(row["C13"]) * ele_mass["C13"]
            + np.float64(row["O18"]) * ele_mass["O18"]
            + np.float64(row["N15"]) * ele_mass["N15"]
            + np.float64(row["H2"]) * ele_mass["H2"]
        )

        mass_base[row["ID"]] = mass_b

        # Calculate mass of the backbone only
        mass_back = (
            np.float64(row["C.1"]) * ele_mass["C"]
            + np.float64(row["O.1"]) * ele_mass["O"]
            + np.float64(row["H.1"]) * ele_mass["H"]
            + np.float64(row["N.1"]) * ele_mass["N"]
            + np.float64(row["P.1"]) * ele_mass["P"]
            + np.float64(row["S.1"]) * ele_mass["S"]
            + np.float64(row["Se.1"]) * ele_mass["Se"]
            + np.float64(row["F.1"]) * ele_mass["F"]
            + np.float64(row["C13.1"]) * ele_mass["C13"]
            + np.float64(row["O18.1"]) * ele_mass["O18"]
            + np.float64(row["N15.1"]) * ele_mass["N15"]
            + np.float64(row["H2.1"]) * ele_mass["H2"]
        )

        mass_backbone[row["ID"]] = mass_back

        # Calculate mass of the whole nucleotide
        mass_nts[row["ID"]] = mass_b + mass_back

    return mass_nts, mass_base, mass_backbone


def inlines_MS1(input_file):
    """
    Read the input file for MS1 (output.3.MS1)
    """
    input_lines = []

    for line in input_file:

        if line[0] != "#":

            if line.split()[2].isdigit():
                input_lines.append(line.rstrip())

    return input_lines


def reorganize_lines(line):
    """
    Order the precursor ion field
    """
    split = line.split()
    new_line = "{} {} {} {} {} {} {} {} {} {}".format(
        split[-3],
        split[-2],
        split[-1],
        split[2],
        split[0],
        split[1],
        split[3],
        split[4],
        split[5],
        split[6],
    )
    return new_line


def lines_with_chemistry(input_lines):
    """
    Prepare lines for the output lines including 3' and 5' chemistry
    """
    new_lines = []

    for line in input_lines:
        new_lines.append(reorganize_lines(line))

    return new_lines


def add_charge(line, charge):
    """
    Add information on the charge to the output lines
    """
    new_line = "{} {} {}".format(
        " ".join(line.split()[:3]), charge, " ".join(line.split()[3:])
    )

    return new_line


def charge_table(input_file):
    """
    Create a dictionary with the charge table for MS1/MS2 ions
    """
    charges_dic = {}

    with open(input_file, "r") as infile:
        for line in infile:

            if line[0].isdigit():
                charges_dic[line.split()[0]] = []

                for ele in line.split()[1].split(","):

                    if ele.isdigit():
                        charges_dic[line.split()[0]].append(ele)

    if "MS1" in input_file or "ms1" in input_file:
        # Define the window for charges on all MS1 fragments, derived from the input charge table file
        global MS1_minz, MS1_z
        MS1_minz, MS1_z = min(
            int(s) for s in min(charges_dic.items(), key=lambda x: x[1])[1]
        ), max(int(s) for s in max(charges_dic.items(), key=lambda x: x[1])[1])

    elif "MS2" in input_file or "ms2" in input_file:
        # Define the window for charges on all MS2 fragments, derived from the input charge table file
        global MS2_minz, MS2_z
        MS2_minz, MS2_z = min(
            int(s) for s in min(charges_dic.items(), key=lambda x: x[1])[1]
        ), max(int(s) for s in max(charges_dic.items(), key=lambda x: x[1])[1])

    return charges_dic


def lines_with_charge(input_lines):
    """
    Writes new lines for each charged species
    """
    new_lines_charge, MS1_charges = [], charge_table(
        os.getcwd() + "/" + args.MS1_charges
    )
    MS1_maxlength, MS1_minlength = max(int(s) for s in MS1_charges.keys()), min(
        int(s) for s in MS1_charges.keys()
    )

    for line in input_lines:

        # The window of fragments length is defined by the intervals given in the charge table input files
        length = len(line.split()[4])
        if MS1_minlength <= length <= MS1_maxlength:

            for ele in MS1_charges[str(len(line.split()[4]))]:
                new_lines_charge.append(add_charge(line, args.ion_mode + str(ele)))

    return new_lines_charge


def add_masses(line, mass_light, mass_heavy):
    """
    Add m/z information in the output lines
    """
    new_line = "{} {} {}\n".format(
        round_masses(mass_light), round_masses(mass_heavy), line
    )

    return new_line


def lines_final(
    input_lines, mzlow, mzhigh, nts_light=nts_mass(read_excel_input(args.nts_light))[0]
):
    """
    Prepare the final output lines
    """
    output_lines = []
    if args.nts_heavy:
        nts_heavy = nts_mass(read_excel_input(args.nts_heavy))[0]
    else:
        nts_heavy = nts_light

    for line in input_lines:
        h_mass, l_mass = 0, 0

        # Add the basic masses of the nucleotides (neutral state) present in the fragment
        for a in line.split()[5]:
            l_mass, h_mass = l_mass + nts_light[a], h_mass + nts_heavy[a]

        # Add masses for the 5'end of the fragments
        if line.split()[8] == "OH":
            l_mass, h_mass = (
                l_mass + ele_mass["O"] + ele_mass["H"],
                h_mass + ele_mass["O"] + ele_mass["H"],
            )

        elif line.split()[8] == "P":
            l_mass, h_mass = (
                l_mass + ele_mass["P"] + ele_mass["O"] * 4 + ele_mass["H"] * 2,
                h_mass + ele_mass["P"] + ele_mass["O"] * 4 + ele_mass["H"] * 2,
            )

        else:
            l_mass, h_mass = (
                l_mass + ele_mass["P"] + ele_mass["O"] * 3 + ele_mass["H"],
                h_mass + ele_mass["P"] + ele_mass["O"] * 3 + ele_mass["H"],
            )

        # Add masses for the 3' end of the fragments
        # If fragment has 3' OH subtract from its mass -PO3 (all fragments are considered neutral by default)
        if line.split()[7] == "OH":
            l_mass, h_mass = (
                l_mass - ele_mass["P"] - ele_mass["O"] * 3,
                h_mass - ele_mass["P"] - ele_mass["O"] * 3,
            )

        # If fragment has 3' P adds a -H to the mass (all fragments are considered neutral by default)
        elif line.split()[7] == "P":
            l_mass, h_mass = l_mass + ele_mass["H"], h_mass + ele_mass["H"]

        # If fragment has 3'>P subtract from its mass -OH (all fragments are considered neutral by default)
        elif line.split()[7] == "cP":
            l_mass, h_mass = (
                l_mass - ele_mass["O"] - ele_mass["H"],
                h_mass - ele_mass["O"] - ele_mass["H"],
            )

        # Add the right amount of hydrogen atoms depending on the fragment charge (starting charge is 0 by default)
        if args.ion_mode == "+":
            l_mass, h_mass = l_mass + ele_mass["H"] * (
                int(line.split()[3][1])
            ), h_mass + ele_mass["H"] * (int(line.split()[3][1]))

        # Subtract the right amount of hydrogen atoms depending on the fragment charge
        # (starting charge is 0 by default)
        if args.ion_mode == "-":
            l_mass, h_mass = l_mass - ele_mass["H"] * (
                int(line.split()[3][1])
            ), h_mass - ele_mass["H"] * (int(line.split()[3][1]))

        # Calculate the m/z for each fragment
        l_mass, h_mass = l_mass / int(line.split()[3][1:]), h_mass / int(
            line.split()[3][1:]
        )

        # Add the line to the list only if its light mass is > mzlow and < mzhigh
        if mzlow < l_mass < mzhigh:
            if args.nts_heavy:
                output_lines.append(add_masses(line, l_mass, h_mass))

            else:
                output_lines.append(add_masses(line, l_mass, "-"))

    return output_lines


def header_info_MS1(input_file):
    """
    Write the header section for the MS1 output file
    """
    header_lines = []

    if args.ion_mode == "+":
        header_lines.append("#ION_MODE positive\n")

    elif args.ion_mode == "-":
        header_lines.append("#ION_MODE negative\n")

    header_lines.append("#MZLOW_MS1 " + str(args.MS1_mzlow) + "\n")
    header_lines.append("#MZHIGH_MS1 " + str(args.MS1_mzhigh) + "\n")
    header_lines.append("#NTS_LIGHT " + str(args.nts_light) + "\n")

    if args.nts_heavy:
        header_lines.append("#NTS_HEAVY " + str(args.nts_heavy) + "\n")

    for line in input_file:

        if line[0] == "#":
            header_lines.append(line)

    header_lines.append(
        "m/z_light m/z_heavy molecule residue_start residue_end charge miss sequence sequence_mod 3'end 5'end "
        "num_copy molecule_location\n"
    )

    return header_lines


# Control if options are correctly given and if there are differences
# between nts dictionaries specified here and in previous scripts
__controls()
out_files = []

if os.path.exists(os.getcwd() + "/output.3.MS1"):

    charge_table(os.getcwd() + "/" + args.MS1_charges)
    # Write all the lines inside the standard output file "Digest_MS1"
    open(os.getcwd() + "/Digest_MS1.txt", "w").writelines(
        header_info_MS1(open(os.getcwd() + "/output.3.MS1", "r"))
        + lines_final(
            lines_with_charge(
                lines_with_chemistry(
                    inlines_MS1(open(os.getcwd() + "/output.3.MS1", "r"))
                )
            ),
            args.MS1_mzlow,
            args.MS1_mzhigh,
        )
    )
    out_files.append("Digest_MS1.txt")

else:
    print(
        "WARNING! MS1 file output.3.MS1 from 3_consolidate.py is missing, MS1 digest will not be generated"
    )

################################# MS2 SPECIFIC WORKFLOW #############################################
"""
This part is executed only under the condition that the file output.3.MS2 is present in the directory
"""

# Checking if the input file output.3.MS2 is present
if os.path.exists(os.getcwd() + "/output.3.MS2"):

    def inlines_MS2(input_file=open(os.getcwd() + "/output.3.MS2", "r")):
        """
        Read the line from the input file for MS2
        """
        input_lines = []

        for line in input_file:
            # Extracting the minimum length of fragments considered for MS2 fragmentation
            if "MIN_LENGTH" in line:
                global min_length_MS2
                min_length_MS2 = int(line.split()[1])

            if line[0] != "#" and line.split():

                if line.split()[2].isdigit():
                    input_lines.append(line[:-1])

        return input_lines

    def fragment_MS2_masses(
        line,
        MS2_charge_dic,
        nts_dic_heavy,
        nts_dic_light=nts_mass(read_excel_input(args.nts_light))[0],
    ):
        """
        Calculate the masses of all the fragments filtered for MS2 analysis
        """
        output_masses, charge_prec, mass_prec = (
            [],
            int(line.split()[5][1:]),
            np.float64(line.split()[0]),
        )
        chem3prime, chem5prime = line.split()[10], line.split()[9]

        # Correction to the charges for charged losses
        charged_loss = charge_prec - 1

        # Mass correction to apply for positive/negative mode in case of charged losses
        if args.ion_mode == "-":
            freebase_correction = 0
            # In case of a charged loss in negative mode, the mass needs no adjustments
            charge_correction = 0
        else:
            # Correct the m/z of free bases in positive mode adding two protons since they are charged +1
            freebase_correction = 2 * ele_mass["H"]
            # Subtract two protons in positive mode when a positive charge is lost due to charged loss
            charge_correction = -2 * ele_mass["H"]

        # Add the ion M-H2O as first entry of the MS2 ions list
        MH2O_mz = mass_prec + (dic_M_x_series["M-H2O"]) / charge_prec

        # Keep the ion if its m/z is in the given interval for MS2 ions
        if args.MS2_mzhigh >= MH2O_mz >= args.MS2_mzlow:
            output_masses.append(
                "M-H2O({}):{}".format(line.split()[5], str(round_masses(MH2O_mz)))
            )

        if chem3prime == "P" or chem5prime == "P":
            # Add the neutral phosphate loss ions M-PO3H and M-PO4H3 to the MS2 list if 3' end is P or OH
            MPO3H_mz = mass_prec + (dic_M_x_series["M-PO3H"]) / charge_prec

            # Keep the ion if its m/z is in the given interval for MS2 ions
            if args.MS2_mzhigh >= MPO3H_mz >= args.MS2_mzlow:
                output_masses.append(
                    "M-P({}):{}".format(line.split()[5], str(round_masses(MPO3H_mz)))
                )

            MPO4H3_mz = mass_prec + (dic_M_x_series["M-PO4H3"]) / charge_prec

            # Keep the ion if its m/z is in the given interval for MS2 ions
            if args.MS2_mzhigh >= MPO4H3_mz >= args.MS2_mzlow:
                output_masses.append(
                    "M-H2O-P({}):{}".format(
                        line.split()[5], str(round_masses(MPO4H3_mz))
                    )
                )

            # Add the charged phosphate loss ions M-PO3- and M-PO4H2- to the MS2 list
            # if 3' end is P and if the precursor has a charge greater than 1
            if charge_prec > 1:
                MPO3_mz = (
                    mass_prec * charge_prec
                    + dic_M_x_series["M-PO3"]
                    + charge_correction
                ) / charged_loss

                # Keep the ion if its m/z is in the given interval for MS2 ions
                if args.MS2_mzhigh >= MPO3_mz >= args.MS2_mzlow:
                    output_masses.append(
                        "M-P({}):{}".format(
                            line.split()[5][0] + str(charged_loss),
                            str(round_masses(MPO3_mz)),
                        )
                    )

                MPO4H2_mz = (
                    mass_prec * charge_prec
                    + dic_M_x_series["M-PO4H2"]
                    + charge_correction
                ) / charged_loss

                # Keep the ion if its m/z is in the given interval for MS2 ions
                if args.MS2_mzhigh >= MPO4H2_mz >= args.MS2_mzlow:
                    output_masses.append(
                        "M-H2O-P({}):{}".format(
                            line.split()[5][0] + str(charged_loss),
                            str(round_masses(MPO4H2_mz)),
                        )
                    )

        elif chem3prime == "cP":
            # Add the charged phosphate loss ions M-PO3-  to the MS2 list
            # if 3' end is cP and if the precursor has a charge greater than 1
            if charge_prec > 1:
                MPO3_mz = (
                    mass_prec * charge_prec
                    + dic_M_x_series["M-PO3"]
                    + charge_correction
                ) / charged_loss
                # If m/z is in the given interval for MS2, result is printed
                if args.MS2_mzhigh >= MPO3_mz >= args.MS2_mzlow:
                    output_masses.append(
                        "M-P({}):{}".format(
                            line.split()[5][0] + str(charged_loss),
                            str(round_masses(MPO3_mz)),
                        )
                    )

        # Add the free bases B- ions and M-B-/M-BH/M-P-B to the MS2 list
        unique_seq = set(list(line.split()[7]))
        last_nt = list(line.split()[7])[-1]

        for b in unique_seq:

            if line.split()[1] == "light":
                output_string = "{}({}1):{}".format(
                    b,
                    args.ion_mode,
                    str(round_masses(nts_dic_onlyB_light[b] + freebase_correction)),
                )
                if output_string not in output_masses:
                    output_masses.append(output_string)

                # The charged base loss ion M-B- is generated only for ions with charge > 1
                if charge_prec > 1:
                    MB_mz = (
                        np.float64(line.split()[0]) * charge_prec
                        + charge_correction
                        - nts_dic_onlyB_light[b]
                    ) / charged_loss

                    # If m/z is in the given interval for MS2, result is printed
                    if args.MS2_mzhigh >= MB_mz >= args.MS2_mzlow:
                        output_string = "M-{}({}):{}".format(
                            b,
                            line.split()[5][0] + str(charged_loss),
                            str(round_masses(MB_mz)),
                        )
                        if output_string not in output_masses:
                            output_masses.append(output_string)

                    if chem3prime == "P" or chem5prime == "P":
                        # Add the charged simultaneous loss of both P and B
                        MBP_mz = (
                            np.float64(line.split()[0]) * charge_prec
                            + charge_correction
                            - nts_dic_onlyB_light[b]
                            + dic_M_x_series["M-PO3H"]
                        ) / charged_loss

                        # Keep the ion if its m/z is in the given interval for MS2 ions
                        if args.MS2_mzhigh >= MBP_mz >= args.MS2_mzlow:
                            output_string = "M-P-{}({}):{}".format(
                                b,
                                line.split()[5][0] + str(charged_loss),
                                str(round_masses(MBP_mz)),
                            )
                            if output_string not in output_masses:
                                output_masses.append(output_string)

                    elif chem3prime == "cP":
                        # Add the charged simultaneous loss of both P and the 3' base B
                        MBP_mz = (
                            np.float64(line.split()[0]) * charge_prec
                            + charge_correction
                            - nts_dic_onlyB_light[last_nt]
                            + dic_M_x_series["M-PO3H"]
                        ) / charged_loss

                        # Keep the ion if its m/z is in the given interval for MS2 ions
                        if args.MS2_mzhigh >= MBP_mz >= args.MS2_mzlow:
                            output_string = "M-P-{}({}):{}".format(
                                last_nt,
                                line.split()[5][0] + str(charged_loss),
                                str(round_masses(MBP_mz)),
                            )
                            if output_string not in output_masses:
                                output_masses.append(output_string)

                        # Add the special case of base double loss (with one being the 3'end base) for cP 3' chemistry
                        if b in line.split()[7][:-1]:
                            MBB_mz = (
                                np.float64(line.split()[0]) * charge_prec
                                + charge_correction
                                - nts_dic_onlyB_light[b]
                                - nts_dic_onlyB_light[last_nt]
                            ) / charged_loss

                            # Keep the ion if its m/z is in the given interval for MS2 ions
                            if args.MS2_mzhigh >= MBB_mz >= args.MS2_mzlow:
                                output_string = "M-{}-{}({}):{}".format(
                                    b,
                                    last_nt,
                                    line.split()[5][0] + str(charged_loss),
                                    str(round_masses(MBB_mz)),
                                )
                                if output_string not in output_masses:
                                    output_masses.append(output_string)

                # The neutral base loss ion M-B is generated for all the precursor ions
                MBH_mz = (
                    np.float64(line.split()[0])
                    - (nts_dic_onlyB_light[b] + ele_mass["H"]) / charge_prec
                )

                # Keep the ion if its m/z is in the given interval for MS2 ions
                if args.MS2_mzhigh >= MBH_mz >= args.MS2_mzlow:
                    output_masses.append(
                        "M-{}({}):{}".format(
                            b, line.split()[5], str(round_masses(MBH_mz))
                        )
                    )

                if chem3prime == "P" or chem5prime == "P":
                    # Add the neutral simultaneous loss of both P and B
                    MBHP_mz = (
                        np.float64(line.split()[0])
                        - (
                            nts_dic_onlyB_light[b]
                            + ele_mass["H"]
                            - dic_M_x_series["M-PO3H"]
                        )
                        / charge_prec
                    )

                    # Keep the ion if its m/z is in the given interval for MS2 ions
                    if args.MS2_mzhigh >= MBHP_mz >= args.MS2_mzlow:
                        output_string = "M-P-{}({}):{}".format(
                            b, line.split()[5], str(round_masses(MBHP_mz))
                        )
                        if output_string not in output_masses:
                            output_masses.append(output_string)

                elif chem3prime == "cP":
                    # Add the special case of base double loss (with one being the 3'end base) for cP 3' chemistry
                    if b in line.split()[7][:-1]:
                        MBHBH_mz = (
                            np.float64(line.split()[0])
                            - (
                                nts_dic_onlyB_light[b]
                                + ele_mass["H"]
                                + nts_dic_onlyB_light[last_nt]
                            )
                            / charge_prec
                        )

                        # Keep the ion if its m/z is in the given interval for MS2 ions
                        if args.MS2_mzhigh >= MBHBH_mz >= args.MS2_mzlow:
                            output_string = "M-{}-{}({}):{}".format(
                                b, last_nt, line.split()[5], str(round_masses(MBHBH_mz))
                            )
                            if output_string not in output_masses:
                                output_masses.append(output_string)

            elif line.split()[1] == "heavy":
                output_masses.append(
                    "{}({}1):{}".format(
                        b,
                        args.ion_mode,
                        str(round_masses(nts_dic_onlyB_heavy[b]) + freebase_correction),
                    )
                )

                # The charged base loss ion M-B- is generated only for ions with charge > 1
                if charge_prec > 1:
                    MBh_mz = (
                        np.float64(line.split()[0]) * charge_prec
                        + charge_correction
                        - nts_dic_onlyB_heavy[b]
                    ) / charged_loss

                    # Keep the ion if its m/z is in the given interval for MS2 ions
                    if args.MS2_mzhigh >= MBh_mz >= args.MS2_mzlow:
                        output_string = "M-{}({}):{}".format(
                            b,
                            line.split()[5][0] + str(charged_loss),
                            str(round_masses(MBh_mz)),
                        )
                        if output_string not in output_masses:
                            output_masses.append(output_string)

                    if chem3prime == "P" or chem5prime == "P":
                        # Add the charged simultaneous loss of both P and B
                        MBPh_mz = (
                            np.float64(line.split()[0]) * charge_prec
                            + charge_correction
                            - nts_dic_onlyB_heavy[b]
                            + dic_M_x_series["M-PO3H"]
                        ) / charged_loss

                        # Keep the ion if its m/z is in the given interval for MS2 ions
                        if args.MS2_mzhigh >= MBPh_mz >= args.MS2_mzlow:
                            output_string = "M-P-{}({}):{}".format(
                                b,
                                line.split()[5][0] + str(charged_loss),
                                str(round_masses(MBPh_mz)),
                            )
                            if output_string not in output_masses:
                                output_masses.append(output_string)

                    elif chem3prime == "cP":
                        # Add the charged simultaneous loss of both P and the 3' base B
                        MBPh_mz = (
                            np.float64(line.split()[0]) * charge_prec
                            + charge_correction
                            - nts_dic_onlyB_heavy[last_nt]
                            + dic_M_x_series["M-PO3H"]
                        ) / charged_loss

                        # Keep the ion if its m/z is in the given interval for MS2 ions
                        if args.MS2_mzhigh >= MBPh_mz >= args.MS2_mzlow:
                            output_string = "M-P-{}({}):{}".format(
                                last_nt,
                                line.split()[5][0] + str(charged_loss),
                                str(round_masses(MBPh_mz)),
                            )
                            if output_string not in output_masses:
                                output_masses.append(output_string)

                        # Add the special case of base double loss (with one being the 3'end base) for cP 3' chemistry
                        if b in line.split()[7][:-1]:
                            MBBh_mz = (
                                np.float64(line.split()[0]) * charge_prec
                                + charge_correction
                                - nts_dic_onlyB_heavy[b]
                                - nts_dic_onlyB_heavy[last_nt]
                            ) / charged_loss

                            # Keep the ion if its m/z is in the given interval for MS2 ions
                            if args.MS2_mzhigh >= MBBh_mz >= args.MS2_mzlow:
                                output_string = "M-{}-{}({}):{}".format(
                                    b,
                                    last_nt,
                                    line.split()[5][0] + str(charged_loss),
                                    str(round_masses(MBBh_mz)),
                                )
                                if output_string not in output_masses:
                                    output_masses.append(output_string)

                MBHh_mz = (
                    np.float64(line.split()[0])
                    - (nts_dic_onlyB_heavy[b] + ele_mass["H"]) / charge_prec
                )

                # Keep the ion if its m/z is in the given interval for MS2 ions
                if args.MS2_mzhigh >= MBHh_mz >= args.MS2_mzlow:
                    output_string = "M-{}({}):{}".format(
                        b, line.split()[5], str(round_masses(MBHh_mz))
                    )
                    if output_string not in output_masses:
                        output_masses.append(output_string)

                if chem3prime == "P" or chem5prime == "P":
                    # Add the neutral simultaneous loss of both P and B
                    MBHPh_mz = (
                        np.float64(line.split()[0])
                        - (
                            nts_dic_onlyB_heavy[b]
                            + ele_mass["H"]
                            - dic_M_x_series["M-PO3H"]
                        )
                        / charge_prec
                    )

                    # Keep the ion if its m/z is in the given interval for MS2 ions
                    if args.MS2_mzhigh >= MBHPh_mz >= args.MS2_mzlow:
                        output_string = "M-P-{}({}):{}".format(
                            b, line.split()[5], str(round_masses(MBHPh_mz))
                        )
                        if output_string not in output_masses:
                            output_masses.append(output_string)

                elif chem3prime == "cP":
                    # Add the special case of base double loss (with one being the 3'end base) for cP 3' chemistry
                    if b in line.split()[7][:-1]:
                        MBHBHh_mz = (
                            np.float64(line.split()[0])
                            - (
                                nts_dic_onlyB_heavy[b]
                                + ele_mass["H"]
                                + nts_dic_onlyB_heavy[last_nt]
                            )
                            / charge_prec
                        )

                        # Keep the ion if its m/z is in the given interval for MS2 ions
                        if args.MS2_mzhigh >= MBHBHh_mz >= args.MS2_mzlow:
                            output_string = "M-{}-{}({}):{}".format(
                                b,
                                last_nt,
                                line.split()[5],
                                str(round_masses(MBHBHh_mz)),
                            )
                            if output_string not in output_masses:
                                output_masses.append(output_string)

        # Loop through all the CID series to output the sequence-defining fragment ion masses
        for ion in list(set(args.CID_series)):
            sequence = list(line.split()[7])

            # If a ion from a,a-B, b,c or d series has to be calculated, the fragment sequence is read from
            # first to last nucleotide
            if ion == "a" or ion == "a-B" or ion == "b" or ion == "c" or ion == "d":
                sequence = sequence

            # If a ion different from a,a-B, b,c or d series has to be calculated, the fragment sequence is read from
            # last to first nucleotide
            else:
                sequence = list(reversed(sequence))

            for i in range(1, len(sequence)):

                # Keep only MS2 fragments with length within specified input (charges_MS2)
                if str(i) in MS2_charge_dic.keys():

                    mass_fragment, mass_fragment_3OH = 0, 0

                    # Calculate the mass of the fragment up to the last nucleotide (standard masses for neutral nts)
                    for nt in sequence[: i - 1]:

                        # Add the masses for light nts
                        if line.split()[1] == "light":
                            mass_fragment += nts_dic_light[nt]

                        # Add the masses for heavy nts
                        else:
                            mass_fragment += nts_dic_heavy[nt]

                    # Add/remove the proper amount of mass depending on the CID ion type for light nts
                    if line.split()[1] == "light":
                        # Dealing with the special case of 3'OH series
                        if ion == "y-P" or ion == "z-P":
                            mass_fragment += (
                                nts_dic_light[sequence[i - 1]]
                                + dic_CID_series_masses[ion[0]]
                            )

                        else:
                            mass_fragment += (
                                nts_dic_light[sequence[i - 1]]
                                + dic_CID_series_masses[ion]
                            )

                        # If also the base is lost, remove the mass corresponding to the base
                        # (stored in nts_dic_onlyB_light)
                        if ion == "a-B":
                            mass_fragment -= nts_dic_onlyB_light[sequence[i - 1]]

                    # Add/remove the proper amount of mass depending on the CID ion type for heavy nts
                    else:

                        # Dealing with the special case of 3'OH series
                        if ion == "y-P" or ion == "z-P":
                            mass_fragment += (
                                nts_dic_heavy[sequence[i - 1]]
                                + dic_CID_series_masses[ion[0]]
                            )

                        else:
                            mass_fragment += (
                                nts_dic_heavy[sequence[i - 1]]
                                + dic_CID_series_masses[ion]
                            )

                        # If also the base is lost, remove the mass corresponding to the base
                        # (stored in nts_dic_onlyB_heavy)
                        if ion == "a-B":
                            mass_fragment -= nts_dic_onlyB_heavy[sequence[i - 1]]

                    if (
                        ion == "a"
                        or ion == "a-B"
                        or ion == "b"
                        or ion == "c"
                        or ion == "d"
                    ):

                        # Edit the mass of the ion based on the 5' end
                        # Add the 5'-OH end mass to the fragment
                        if chem5prime == "OH":
                            mass_fragment += ele_mass["O"] + ele_mass["H"]

                        # Add the 5'-P end mass to the fragment
                        if chem5prime == "P":
                            mass_fragment += (
                                ele_mass["O"] * 4 + ele_mass["H"] * 2 + ele_mass["P"]
                            )

                    else:

                        # Add the 3'-OH end mass to the fragment
                        if chem3prime == "OH":
                            mass_fragment = (
                                mass_fragment - ele_mass["P"] - ele_mass["O"] * 3
                            )

                        # Add the 3'-P end mass to the fragment
                        elif chem3prime == "P":
                            mass_fragment += ele_mass["H"]

                            # Adds 3'OH-y and 3'-OH-z ions in case the 3' end is P
                            if ion == "y-P" or ion == "z-P":
                                mass_fragment_3OH = (
                                    mass_fragment + dic_CID_series_masses[ion]
                                )

                        # Add the 3'>P end mass to the fragment
                        elif chem3prime == "cP":
                            mass_fragment = (
                                mass_fragment - ele_mass["O"] - ele_mass["H"]
                            )

                    # Calculate m/z for MS2 ions with charges specified in the charge table input
                    for char in MS2_charge_dic[str(i)]:

                        # Sanity check to exclude MS2 ions with charges larger than the precursor
                        if int(char) <= charge_prec:

                            # Add the right amount of hydrogen atoms depending on the fragment charge
                            # (starting charge is 0 by default)
                            if args.ion_mode == "+":
                                mass_charged = mass_fragment + ele_mass["H"] * int(char)

                                if mass_fragment_3OH:
                                    mass_charged_3OH = mass_fragment_3OH + ele_mass[
                                        "H"
                                    ] * int(char)

                            # Remove the right amount of hydrogen atoms depending on the fragment charge
                            # (starting charge is 0 by default)
                            elif args.ion_mode == "-":
                                mass_charged = mass_fragment - ele_mass["H"] * int(char)

                                if mass_fragment_3OH:
                                    mass_charged_3OH = mass_fragment_3OH - ele_mass[
                                        "H"
                                    ] * int(char)

                            mz_fragment = mass_charged / int(char)

                            if mass_fragment_3OH:
                                mz_fragment_3OH = mass_charged_3OH / int(char)

                            else:
                                mz_fragment_3OH = 0

                            # Keep the ion if its m/z is in the given interval for MS2 ions
                            if (
                                args.MS2_mzhigh >= mz_fragment >= args.MS2_mzlow
                                and ion != "y-P"
                                and ion != "z-P"
                            ):

                                # Output the a-B series with the number after the a
                                if ion != "a-B":
                                    output_masses.append(
                                        ion
                                        + str(i)
                                        + "("
                                        + args.ion_mode
                                        + str(char)
                                        + "):"
                                        + str(round_masses(mz_fragment))
                                    )

                                else:
                                    output_masses.append(
                                        ion[0]
                                        + str(i)
                                        + "-B("
                                        + args.ion_mode
                                        + str(char)
                                        + "):"
                                        + str(round_masses(mz_fragment))
                                    )

                            if args.MS2_mzhigh >= mz_fragment_3OH >= args.MS2_mzlow:

                                # Output the a-B series with the number after the a
                                if ion != "a-B" and ion != "y-P" and ion != "z-P":
                                    output_masses.append(
                                        ion
                                        + str(i)
                                        + "("
                                        + args.ion_mode
                                        + str(char)
                                        + "):"
                                        + str(round_masses(mz_fragment_3OH))
                                    )

                                else:
                                    output_masses.append(
                                        ion[0]
                                        + str(i)
                                        + ion[1:]
                                        + "("
                                        + args.ion_mode
                                        + str(char)
                                        + "):"
                                        + str(round_masses(mz_fragment_3OH))
                                    )

        return output_masses

    def final_lines_MS2(lines_MS2):
        """
        Add the m/z of fragments ions to the final lines for the output
        """
        output_lines = []

        # Define two variables to keep track of the number of unique sequences of targets and decoys
        global tot_targets
        tot_targets = 0
        global tot_decoys
        tot_decoys = 0

        if args.nts_heavy:
            nts_dic_heavy = nts_mass(read_excel_input(args.nts_heavy))[0]
        else:
            nts_dic_heavy = {}

        for line in lines_MS2:
            output_lines.append(
                " ".join(
                    line.split()
                    + fragment_MS2_masses(line, MS2_charge_table, nts_dic_heavy)
                    + list("\n")
                )
            )

            # Add the targets and decoys to the respective counters
            split = line.split()
            if "decoy" in split[2]:
                tot_decoys += 1

            else:
                tot_targets += 1

        return output_lines

    def header_info_MS2(input_file):
        """
        Create the header for the output file
        """
        header_lines, min_length = [], None

        for line in input_file:

            if line[0] == "#" and "MIN_LENGTH" not in line:
                header_lines.append(line)
                if "#INPUT_SEQUENCE" in line:
                    global input_sequence
                    input_sequence = line.split()[1].split(".fasta")[0]
            if "#MIN_LENGTH" in line:
                min_length = line

        if min_length:
            header_lines.append(min_length)

        if args.ion_mode == "+":
            header_lines.append("#ION_MODE positive\n")

        elif args.ion_mode == "-":
            header_lines.append("#ION_MODE negative\n")

        header_lines.append(
            "#CID_SERIES " + " ".join(list(set(args.CID_series))) + "\n"
        )
        header_lines.append("#MZLOW_MS2 " + str(args.MS2_mzlow) + "\n")
        header_lines.append("#MZHIGH_MS2 " + str(args.MS2_mzhigh) + "\n")
        header_lines.append("#MZLOW_MS1 " + str(args.MS1_mzlow) + "\n")
        header_lines.append("#MZHIGH_MS1 " + str(args.MS1_mzhigh) + "\n")
        header_lines.append(
            "#ELEMENTAL_COMPOSITION_LIGHT " + str(args.nts_light) + "\n"
        )

        if args.nts_heavy:
            header_lines.append(
                "#ELEMENTAL_COMPOSITION_HEAVY " + str(args.nts_heavy) + "\n"
            )

        header_lines.append("#SEQX_CONSOLIDATION " + str(args.mz_consolidation) + "\n")

        if args.mz_consolidation == "y":
            header_lines.append(
                "#MS1_SEQX_PPM " + str(args.MS1_ppm_consolidation) + "\n"
            )
            header_lines.append(
                "#MS2_SEQX_PPM " + str(args.MS2_ppm_consolidation) + "\n"
            )

        return header_lines

    # Create two new dictionaries for a-B fragments (nucleobases)
    nts_dic_onlyB_light = nts_mass(read_excel_input(args.nts_light))[1]
    if args.nts_heavy:
        nts_dic_onlyB_heavy = nts_mass(read_excel_input(args.nts_heavy))[1]

    lines_MS2 = []

    for line in lines_final(
        lines_with_charge(lines_with_chemistry(inlines_MS2())),
        args.MS1_mzlow,
        args.MS1_mzhigh,
    ):

        split = line.split()
        # Only fragments longer than the specified cutoff for MS2 ions are kept
        if len(split[7]) >= min_length_MS2:

            # Only fragments with m/z in specified MS1 interval are considered
            if args.MS1_mzhigh >= np.float64(split[0]) >= args.MS1_mzlow:
                lines_MS2.append(
                    "{} {} {} {} {} {}".format(
                        split[0],
                        "light",
                        " ".join(split[2:9]),
                        split[10],
                        split[9],
                        " ".join(split[11:]),
                    )
                )

            if args.nts_heavy:
                if args.MS1_mzhigh >= np.float64(split[1]) >= args.MS1_mzlow:
                    lines_MS2.append(
                        "{} {} {} {} {} {}".format(
                            split[1],
                            "heavy",
                            " ".join(split[2:9]),
                            split[10],
                            split[9],
                            " ".join(split[11:]),
                        )
                    )

    # Determine a dictionary with the amount of masses to subtract (-) or add (+) to nts for the corresponding
    # type of CID ion. The difference is compared to a nt in neutral state within a chain, no 3' or 5' ends
    dic_CID_series_masses = {
        "a": -(ele_mass["P"] + ele_mass["O"] * 4 + ele_mass["H"] * 2),
        "a-B": -(ele_mass["P"] + ele_mass["O"] * 4 + ele_mass["H"] * 3),
        "b": -(ele_mass["P"] + ele_mass["O"] * 3),
        "c": -(ele_mass["O"] + ele_mass["H"]),
        "d": ele_mass["H"],
        "z": -ele_mass["H"],
        "y": ele_mass["O"] + ele_mass["H"],
        "x": ele_mass["P"] + ele_mass["O"] * 3,
        "w": ele_mass["P"] + ele_mass["O"] * 4 + ele_mass["H"] * 2,
        "z-P": -(ele_mass["H"] + ele_mass["P"] + ele_mass["O"] * 3),
        "y-P": -(ele_mass["H"] + ele_mass["P"] + ele_mass["O"] * 3),
    }

    # Determine a dictionary with the amount of masses to subtract (-) or add (+) to precursor ions (M) to
    # obtain the "M-xx" series
    dic_M_x_series = {
        "M-H2O": -(ele_mass["H"] * 2 + ele_mass["O"]),
        "M-PO3H": -(ele_mass["O"] * 3 + ele_mass["P"] + ele_mass["H"]),
        "M-PO4H3": -(ele_mass["P"] + ele_mass["O"] * 4 + ele_mass["H"] * 3),
        "M-PO3": -(ele_mass["O"] * 3 + ele_mass["P"]),
        "M-PO4H2": -(ele_mass["P"] + ele_mass["O"] * 4 + ele_mass["H"] * 2),
    }

    MS2_charge_table = charge_table(os.getcwd() + "/" + args.MS2_charges)

    # Write the output lines in the output file Digest_MS2.txt
    body_output = final_lines_MS2(lines_MS2)

    # Add the info on unique sequences and decoys in the header
    final_header = (
        header_info_MS2(open(os.getcwd() + "/output.3.MS2", "r"))
        + ["#TARGETS {}\n#DECOYS {}\n".format(tot_targets, tot_decoys)]
        + [
            "m/z isotope molecule_ID residue_start residue_end charge miss sequence "
            "sequence_mod 5'end 3'end num_copy molecule_location CID_series_fragment(charge):m/z\n"
        ]
    )

    open(os.getcwd() + f"/Digest_{input_sequence}.txt", "w").writelines(
        final_header + body_output
    )
    out_files.append(f"Digest_{input_sequence}.txt")

else:
    print(
        "WARNING! MS2 file output.3.MS2 from 3_consolidate.py is missing, MS2 digest will not be calculated"
    )

# m/z based consolidation, where nucleotides that in a particular alphabet are too close
# in masses ppm to be indistinguishable in the matching, are reported as 'X' within their sequence
if args.mz_consolidation == "y":
    digest_lines = ct.mz_consolidate(
        args.nts_light,
        f"Digest_{input_sequence}.txt",
        "light",
        args.MS1_ppm_consolidation,
        args.MS2_ppm_consolidation,
        read_csv(),
    )
    if digest_lines:
        open("test_consolidate.txt", "w").writelines(digest_lines)
        os.remove(os.getcwd() + f"/Digest_{input_sequence}.txt")
        move(
            os.getcwd() + "/test_consolidate.txt",
            os.getcwd() + f"/Digest_{input_sequence}.txt",
        )

    if args.nts_heavy:
        digest_lines = ct.mz_consolidate(
            args.nts_heavy,
            f"Digest_{input_sequence}.txt",
            "heavy",
            args.MS1_ppm_consolidation,
            args.MS2_ppm_consolidation,
            read_csv(),
        )

        open("test_consolidate.txt", "w").writelines(digest_lines)
        os.remove(os.getcwd() + f"/Digest_{input_sequence}.txt")
        move(
            os.getcwd() + "/test_consolidate.txt",
            os.getcwd() + f"/Digest_{input_sequence}.txt",
        )
    print("m/z based consolidation COMPLETED!\n")


else:
    # Check if any combination of two nucleotides in the alphabet(s)
    # provided has masses within 0.5 Dalton, warning the user and asking to run consolidation
    ct.check_Da_nucleotides(args.nts_light)
    if args.nts_heavy:
        ct.check_Da_nucleotides(args.nts_heavy)

print("Done! Output file(s) -> {}".format(" ".join(out_files)))
