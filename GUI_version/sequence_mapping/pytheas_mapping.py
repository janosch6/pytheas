#!/usr/bin/python3

"""
Last update: January 2022
Author: Luigi D'Ascenzo, PhD - The Scripps Research Institute, La Jolla (CA)
Contact info: dascenzoluigi@gmail.com
GitHub project repository: https://github.com/ldascenzo/pytheas

DESCRIPTION
Mapping routine of the Pytheas workflow

OUTPUT
1) mapping_output -> html file with information on the RNA sequences and the mapped sequences
"""

from gooey import Gooey, GooeyParser
from mapping_library import Mapping
import os


@Gooey(
    dump_build_config=True,
    program_name="Pytheas sequence mapping",
    default_size=(1920, 1080),
)
def mapper():
    description = "Generate a graphical output of identified targets mapped on the input RNA sequence(s)"
    parser = GooeyParser(description=description)

    base_path = os.getcwd() + "/Test_data/"

    # Required arguments
    parser.add_argument(
        "Final_report",
        help="Pytheas final report output file",
        widget="FileChooser",
        default=os.getcwd() + "/output/final_report/final_report_test_set.csv",
    )
    parser.add_argument(
        "Nucleotides_list",
        widget="FileChooser",
        help="Elemental composition file for standard and "
        "modified nucleotides (Excel spreadsheet)",
        default=base_path + "nts_light.xlsx",
    )
    parser.add_argument(
        "RNA_sequence",
        widget="FileChooser",
        help="Input RNA sequence in fasta format",
        default=base_path + "test_set_sequences.fasta",
    )

    # Optional arguments
    parser.add_argument(
        "--minimum_targets_length",
        default=3,
        type=int,
        help="Minimum targets length to be mapped on " "the RNA sequence",
    )
    parser.add_argument(
        "--Sp_cutoff",
        default=0,
        type=float,
        help="Minimum Sp score cutoff for targets" "to be mapped on the RNA sequence",
    )

    ####################################################
    args = parser.parse_args()

    output_dir = os.path.join(os.getcwd(), "output/sequence_mapping")
    os.makedirs(output_dir, exist_ok=True)
    os.chdir(output_dir)

    map_sequences = Mapping(
        args.Nucleotides_list,
        args.Final_report,
        args.RNA_sequence,
        args.minimum_targets_length,
        args.Sp_cutoff,
    )

    map_sequences.final_output()


if __name__ == "__main__":
    mapper()
