#!/usr/bin/env python3

"""
Last update: February 2021
Credits to: Luigi D'Ascenzo, PhD - The Scripps Research Institute, La Jolla (CA)
Contact info: dascenzo@scripps.edu

DESCRIPTION
The script outputs the final html file with the mapping scheme for the given RNA sequence and final report file

USAGE
python pytheas_mapping.py --OPTIONS

OPTIONS
--nts_alphabet (REQUIRED) -> Excel spreadsheet with the info on the modification alphabet (the same used for the digest
                             generation)
--input_file (REQUIRED) -> Final report csv file
--input_sequences (REQUIRED) -> fasta file with the original sequence(s) of the RNA molecule(s)
--min_length (OPTIONAL) -> Minimum fragment length to be considered and shown in the mapping scheme
--Sp_cutoff (OPTIONAL, DEFAULT = 0) -> Minimum Sp score cutoff for fragments to be considered for mapping

OUTPUT
Mapping visualization file in html format

"""

import os, sys
import pandas as pd
import argparse
import numpy as np
from Bio import SeqIO
import ntpath

# Initialize and define launch options
parser = argparse.ArgumentParser(description="List of available options")
parser.add_argument(
    "--nts_alphabet",
    required=True,
    help="File with nucleotides and modification alphabet (" "Required)",
)
parser.add_argument(
    "--input_file", required=True, help="Final report csv file (Required)"
)
parser.add_argument(
    "--input_sequences",
    required=True,
    help="Original sequence (fasta) used for the in silico "
    "digestion vs which mapping will be performed",
)
parser.add_argument(
    "--min_length",
    default=3,
    type=int,
    help="Minimum fragment length to be considered in the " "mapping score",
)
parser.add_argument(
    "--Sp_cutoff",
    default=0,
    help="Minimum Sp score cutoff for fragments to be considered for " "mapping",
)

args = parser.parse_args()

std_nts = []


def TakeFourth(elem):
    return elem[3]


def read_excel_input(nts_file):
    """
    Produces a dataframe with all the info on the nucleobases from the input file nts_alphabet_light
    """
    # Checking that the nts_alphabet_light file given in argument exists
    if not os.path.exists(nts_file):
        print(
            "ERROR! File "
            + nts_file
            + " does not exist. Execution terminated without generating any output"
        )
        sys.exit(1)

    # Creates a dataframe with info from Excel spreadsheet
    df = pd.read_excel(nts_file, header=12)

    # Drops rows with NaN values
    df = df[pd.notnull(df["ID"])]

    # Transform all ID values in string (so numbers can be used as one letter code for bases)
    df = df.astype({"ID": str})

    # TEMPORARY SOLUTION
    # Add an 'X' wildcard residue entry in the input alphabet to avoid errors with residues with X
    out_dic = dict(zip(df.ID, df.ID_ext))
    out_dic["X"] = ["X"]

    return out_dic


def read_fasta_seq(fasta_file):
    """
    Read the RNA sequence from a fasta file given as option
    """
    seq_output, seq_dataframes = {}, {}

    with open(fasta_file.rstrip(), "r") as handle:
        # Extract and process the sequences within fasta files
        for seq in SeqIO.parse(handle, "fasta"):

            sequence = str(seq.seq.ungap("-"))
            seq_output[str(seq.id)] = list(sequence)

    # Create dataframes with the sequences
    for key in seq_output.keys():
        df_seq = pd.DataFrame(seq_output[key])

        # Starts the index as 1 since it is a sequence
        df_seq.index = df_seq.index + 1

        df_seq = df_seq.transpose()

        df_seq = df_seq.reset_index()

        # Change the type of column header to string (to avoid type compatibility issues)
        df_seq.columns = df_seq.columns.map(str)

        seq_dataframes[key] = df_seq

    return seq_dataframes


def sort_df(csv_infile):
    """
    Group together all rows belonging to the same molecule and order them alphabetically
    """
    df = pd.read_csv(csv_infile)

    return df.sort_values("sequence_location")


def explode_column(df, lst_cols, fill_value="", preserve_index=False):
    """
    Explodes the values on a dataframe column into multiple columns, keeping the other values intact
    """

    # make sure `lst_cols` is list-alike
    if (
        lst_cols is not None
        and len(lst_cols) > 0
        and not isinstance(lst_cols, (list, tuple, np.ndarray, pd.Series))
    ):
        lst_cols = [lst_cols]

    # all columns except `lst_cols`
    idx_cols = df.columns.difference(lst_cols)

    # calculate lengths of lists
    lens = df[lst_cols[0]].str.len()

    # preserve original index values
    idx = np.repeat(df.index.values, lens)

    # create "exploded" DF
    res = pd.DataFrame(
        {col: np.repeat(df[col].values, lens) for col in idx_cols}, index=idx
    ).assign(**{col: np.concatenate(df.loc[lens > 0, col].values) for col in lst_cols})
    # append those rows that have empty lists
    if (lens == 0).any():
        # at least one list in cells is empty
        res = res.append(df.loc[lens == 0, idx_cols], sort=False).fillna(fill_value)

    # revert the original index order
    res = res.sort_index()

    # reset index if requested
    if not preserve_index:
        res = res.reset_index(drop=True)

    return res


def group_df(df=sort_df(args.input_file)):
    """
    Groups together the istances of matches for the same residue numbers
    """
    df = explode_column(
        df.assign(sequence_location=df.sequence_location.str.split(";")),
        "sequence_location",
    )

    # Sort the values of Sp for matches in descending order
    df = df.sort_values(by=["length", "Score (Sp)"], ascending=[False, False])
    df.reset_index(inplace=True, drop=True)
    df = df.astype({"Score (Sp)": str, "RT": str})

    # Creates a string with the info about a match for a given residue number window
    df["info"] = (
        df["sequence"]
        + "_"
        + df["sequence_mods"]
        + "_"
        + df["isotope"]
        + "_enz_"
        + df["Score (Sp)"]
        + "_"
        + df["RT"]
    )

    return df.groupby("sequence_location".split(";"))["info"].apply(list)


def align_cells(lines):
    """
    Correct the problem of some cells not being aligned in successive columns, when belonging to the same fragment
    sequence
    """
    previous_line, output_lines = None, ["molecule,nres,mod,mod_ext,matches\n"]

    for line in lines:

        output_nts = []

        if previous_line:

            current_nts, previous_nts = (
                line.split(",")[4:],
                previous_line.split(",")[4:],
            )
            output_nts = current_nts

            pairs = []
            for j, previous_nt in reversed(list(enumerate(previous_nts))):
                for i, current_nt in enumerate(current_nts):

                    if (
                        "_".join(current_nt.split("_")[:-2]) in previous_nt
                        and i != j
                        and (i, j) not in pairs
                        and (j, i) not in pairs
                    ):

                        pairs.extend([(i, j), (j, i)])

                        if len(output_nts) < len(previous_nts):
                            output_nts = current_nts + [""] * (
                                len(previous_nts) - len(current_nts)
                            )

                        output_nts[j], output_nts[i] = (
                            "_".join(current_nt.split("_")),
                            output_nts[j],
                        )

                        break

            output_nts[:] = [s.replace("\n", "") for s in output_nts]
            output_nts[-1] = output_nts[-1] + "\n"

            output_lines.append(",".join(line.split(",")[:4] + output_nts))

            previous_line = ",".join(line.split(",")[:4] + output_nts)

        else:
            previous_line = line

    return output_lines


def filter_output(series=group_df(), nts_dic=read_excel_input(args.nts_alphabet)):
    """
    Prepare the output lines with the needed info
    """
    d = {}

    for index, row in series.iteritems():

        # decoy lines are not considered for mapping purposes
        if "decoy" not in index:
            startres, final_residue = int(index.split(",")[1]), int(index.split(",")[2])

            for match in row:

                seq, sp_score = match.split("_")[0], np.float64(match.split("_")[4])
                counter = startres

                # Only fragments longer or equal to min_length parameter are considered for mapping.
                # Also apply Sp score cutoff
                if len(seq) >= args.min_length and sp_score >= args.Sp_cutoff:

                    # Consolidate together all the matches found for a given residue number, they will be the
                    # lines in the final output
                    for nt in seq:

                        if nt not in std_nts:

                            mod_id = "{}+{}+{}+{}".format(
                                index.split(",")[0], counter, nt, nts_dic[nt]
                            )

                            if mod_id in d.keys():

                                # Mark with a @ the terminal residues for each fragment
                                if counter == final_residue:
                                    d[mod_id].append(
                                        "_".join(match.split("_")[2:])
                                        + "_"
                                        + seq
                                        + "_@"
                                    )

                                else:
                                    d[mod_id].append(
                                        "_".join(match.split("_")[2:]) + "_" + seq + "_"
                                    )

                            else:
                                # Mark with a @ the terminal residues for each fragment
                                if counter == final_residue:
                                    d[mod_id] = [
                                        "_".join(match.split("_")[2:])
                                        + "_"
                                        + seq
                                        + "_@"
                                    ]

                                else:
                                    d[mod_id] = [
                                        "_".join(match.split("_")[2:]) + "_" + seq + "_"
                                    ]

                        counter += 1

    return d


def output_lines(dic=filter_output()):
    """
    Output lines
    """
    lines = ["molecule,nres,mod,mod_ext,matches\n"]

    # Create a variable to keep track of the largest amount of matches per line (otherwise pandas will
    # crash on reading the csv)
    global most_matches
    most_matches = 0

    # Read the entries in the dictionary ordering by molecule name and residue number
    for entry in sorted(
        dic.keys(), key=lambda k: (str(k.split("+")[0]), int(k.split("+")[1]))
    ):

        split = entry.split("+")

        # Add an additional term with the id of the base matched
        lines.append(
            "{},{},{},{},{}\n".format(
                split[0],
                split[1],
                split[2],
                split[3],
                ",".join([x + "_" + split[2] for x in dic[entry]]),
            )
        )

        if len(dic[entry]) > most_matches:
            most_matches = len(dic[entry])

    return lines


open("mapping_output_temp.csv", "w").writelines(output_lines())


def consolidate_modifications(infile="mapping_output_temp.csv"):
    """
    Add together rows with unmodified and modified nts on the same position
    """
    # Old syntax, works with older versions of matplotlib
    # df = pd.read_csv(infile, header = None, names = ['molecule' , 'nres' ,'mod', 'mod_ext', 'matches'] +
    # [' '] * (most_matches - 1))
    df = pd.read_csv(
        infile,
        header=None,
        names=["molecule", "nres", "mod", "mod_ext", "matches"]
        + list(range(1, most_matches)),
    )

    # Find the occurrences of nres_molecule with duplicated matches
    duplicated_nres = (
        df[df.duplicated(["molecule", "nres"], keep=False)]["nres"]
        + "_"
        + df[df.duplicated(["molecule", "nres"], keep=False)]["molecule"]
    ).tolist()

    dict_edited_lines, dict_redundants, csv_lines = {}, {}, []

    # Creates a dictionary with all the redundant occurrences of nts for the same nres
    with open(infile, "r") as input_csv:
        for line in input_csv:

            nres_molecule = line.split(",")[1] + "_" + line.split(",")[0]

            if nres_molecule in duplicated_nres:

                if nres_molecule not in dict_redundants.keys():

                    dict_redundants[nres_molecule] = [line.split(",")]

                else:
                    dict_redundants[nres_molecule].append(line.split(","))

    # Combine redundant matches for the same nres on a single line (+ some tricks to selectively
    # introduce new line entries "\n")
    for key in dict_redundants.keys():
        ordered_lines = sorted(dict_redundants[key], key=TakeFourth)

        final_line = ordered_lines[0]
        final_line[:] = [s.replace("\n", "") for s in final_line]

        for i in range(1, len(ordered_lines)):
            ordered_lines[i][:] = [s.replace("\n", "") for s in ordered_lines[i]]
            final_line.extend(ordered_lines[i][4:])

        final_line[-1] = final_line[-1] + "\n"

        dict_edited_lines[key] = final_line

    added_lines = []

    # Write the final csv output
    with open(infile, "r") as input_csv:
        for line in input_csv:
            nres_molecule = line.split(",")[1] + "_" + line.split(",")[0]

            if nres_molecule in duplicated_nres:

                if nres_molecule not in added_lines:
                    csv_lines.append(",".join(dict_edited_lines[nres_molecule]))
                    added_lines.append(nres_molecule)

            else:
                csv_lines.append(line)

    # Align cells belonging to the same residues among different columns
    csv_lines = align_cells(csv_lines)

    return csv_lines


def transpose_df(infile):
    transposed_dfs = {}

    # Old syntax, works with older versions of matplotlib
    df = pd.read_csv(
        infile,
        header=None,
        names=["molecule", "nres", "mod", "mod_ext", "matches"]
        + list(range(1, most_matches)),
    )

    # Create separate dataframes for fragments belonging to different molecules
    molecules = df["molecule"].unique().tolist()[1:]

    for molecule in molecules:
        df_mol = df.loc[(df["molecule"] == molecule) | (df["molecule"] == "molecule")]

        df1 = df_mol.transpose()

        # Set the nres to be the header for the df
        df1.columns = df1.iloc[1]
        df1 = df1.reset_index()

        df1 = df1.drop(["nres", "index"], axis=1)
        transposed_dfs[molecule] = df1

    return transposed_dfs


def merge_dataframes(match_dict, seq_dict=read_fasta_seq(args.input_sequences)):
    """
    Merges the input fasta sequence with the matching results
    """
    html_tables = []

    for seq in seq_dict.keys():

        if seq in match_dict.keys():
            df_out = pd.merge(seq_dict[seq], match_dict[seq], how="outer")

            # Drop columns and rows with redundant or not useful info
            df_out = df_out.drop(columns=["index"])

            # Check if the 4th row has to be deleter or not in the final df
            flag = None
            for ele in df_out.iloc[4]:
                if "light" in str(ele) or "heavy" in str(ele):
                    flag = True
                    break

            if flag:
                df_out = df_out.drop(df_out.index[1:4])

            else:
                df_out = df_out.drop(df_out.index[1:5])

            df_out = df_out.dropna(how="all")
            df_out = df_out.replace(np.nan, "", regex=True)

            html_tables.extend(
                [
                    "<p><strong>{}</strong></p>".format(seq),
                    df_out.to_html(index=False, border=0, justify="center"),
                    "\n\n\n",
                ]
            )

        else:
            print(
                "WARNING!!! The matching info for the sequence of molecule {} has not been found, thus it will be "
                "skipped from the output".format(seq)
            )

    return html_tables


def html_css_header():
    """
    Writes the header for the output html  file with the visualized mapping
    """
    return """<style>
 
 	    table, th, td {
         border-left: none;
         border-right: none;
         border-spacing: 0 5px;
         text-align: center;
         width: 1px;
         height: 15px;
         font-size: 15px;
         font-family:helvetica,sans-serif;
         padding-top: 0;
         padding-bottom:0;
         vertical-align: middle;
  
         }
             p { 
	     padding-left: 15px;
         margin-bottom: 0;}

         </style>
 
         """


def filename_from_path(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)


if __name__ == "__main__":
    open("mapping_output.csv", "w").writelines(consolidate_modifications())

    # os.remove('mapping_output_temp.csv')

    html_lines = [
        html_css_header(),
        " ".join(merge_dataframes(transpose_df("mapping_output.csv"))),
    ]

    html_lines.append(
        """            
            <script src='js/mapping_output.js'> </script>           
            """
    )

    output_name = filename_from_path(args.input_file)[13:-4]

    with open(output_name + "_mapping.html", "w") as _file:
        _file.writelines(html_lines)
