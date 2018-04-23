#!/usr/bin/env python3
# -*- coding: latin-1 -*-
import os.path
import argparse
from dcicutils import submit_utils
import attr
import xlwt
import sys


EPILOG = '''
    To create an xls file with sheets to be filled use the example and modify to your needs.
    It will accept the following parameters.
        --type           use for each sheet that you want to add to the excel workbook
        --descriptions   adds the descriptions in the second line (by default True)
        --enums          adds the list of options for a fields if it has a controlled vocabulary (by default True)
        --comments       adds the comments together with enums (by default False)
        --writexls       creates the xls file (by default True)
        --outfile        change the default file name "fields.xls" to a specified one

    This program graphs uploadable fields (i.e. not calculated properties)
    for a type with optionally included description and enum values.

    To get multiple objects use the '--type' argument multiple times

            %(prog)s --type Biosample --type Biosource

    The '--type' argument can also be used with a few custom options to generate multiple
    sheets, namely 'all', 'HiC', 'Chip-Seq', 'Repliseq', or 'FISH'

            %(prog)s --type HiC

    to include comments (useful tips) for all types use the appropriate flag at the end

            %(prog)s --type Biosample --comments
            %(prog)s --type Biosample --type Biosource --comments

    To change the result filename use --outfile flag followed by the new file name

            %(prog)s --type Biosample --outfile biosample_only.xls
            %(prog)s --type Biosample --type Experiment --outfile my_selection.xls

    '''


def getArgs():  # pragma: no cover
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--type',
                        help="Add a separate --type for each type you want to get or use 'all' to get all sheets.",
                        action="append")
    parser.add_argument('--descriptions',
                        default=True,
                        action='store_true',
                        help="Include descriptions for fields.")
    parser.add_argument('--comments',
                        default=False,
                        action='store_true',
                        help="Include comments for fields")
    parser.add_argument('--enums',
                        default=True,
                        action='store_true',
                        help="Include enums for fields.")
    parser.add_argument('--writexls',
                        default=True,
                        action='store_true',
                        help="Create an xls with the columns and sheets"
                             "based on the data returned from this command.")
    parser.add_argument('--key',
                        default='default',
                        help="The keypair identifier from the keyfile.  \
                        Default is --key=default")
    parser.add_argument('--keyfile',
                        default=os.path.expanduser("~/keypairs.json"),
                        help="The keypair file.  Default is --keyfile=%s" %
                             (os.path.expanduser("~/keypairs.json")))
    parser.add_argument('--debug',
                        default=False,
                        action='store_true',
                        help="Print debug messages.  Default is False.")
    parser.add_argument('--outfile',
                        default='fields.xls',
                        help="The name of the output file. Default is fields.xls")
    parser.add_argument('--remote',
                        default=False,
                        action='store_true',
                        help="will skip attribution prompt \
                        needed for automated submissions")
    args = parser.parse_args()
    return args


@attr.s
class FieldInfo(object):
    name = attr.ib()
    ftype = attr.ib()
    lookup = attr.ib()
    desc = attr.ib(default=u'')
    comm = attr.ib(default=u'')
    enum = attr.ib(default=u'')

# additional fields for experiment sheets to capture experiment_set related information
exp_set_addition = [FieldInfo('*replicate_set', 'Item:ExperimentSetReplicate', 3, 'Grouping for replicate experiments'),
                    FieldInfo('*bio_rep_no', 'integer', 4, 'Biological replicate number'),
                    FieldInfo('*tec_rep_no', 'integer', 5, 'Technical replicate number'),
                    # FieldInfo('experiment_set', 'array of Item:ExperimentSet', 2,
                    #          'Grouping for non-replicate experiments')
                    ]


fetch_items = {
    "Document": "document",
    "Protocol": "protocol",
    "Enzyme": "enzyme",
    "Biosource": "biosource",
    "Publication": "publication",
    "Vendor": "vendor"
    }


sheet_order = [
    "User", "Award", "Lab", "Document", "Protocol", "Publication", "Organism",
    "IndividualMouse", "IndividualHuman", "Vendor", "Enzyme", "Construct", "TreatmentRnai",
    "TreatmentChemical", "GenomicRegion", "Target", "Antibody", "Modification",
    "Biosource", "Biosample", "BiosampleCellCulture", "Image", "FileFastq", "FileFasta",
    "FileProcessed", "FileReference", "FileCalibration", "FileSet", "FileSetCalibration",
    "MicroscopeSettingD1", "MicroscopeSettingD2", "MicroscopeSettingA1", "MicroscopeSettingA2",
    "FileMicroscopy", "FileSetMicroscopeQc", "ImagingPath", "ExperimentMic", "ExperimentMic_Path",
    "ExperimentHiC", "ExperimentCaptureC", "ExperimentRepliseq", "ExperimentAtacseq",
    "ExperimentChiapet", "ExperimentDamid", "ExperimentSeq", "ExperimentSet",
    "ExperimentSetReplicate", "WorkflowRunSbg", "WorkflowRunAwsem", "OntologyTerm"
    ]


def sort_item_list(item_list, item_id, field):
    """Sort all items in list alphabetically based on values in the given field and bring item_id to beginning."""
    # sort all items based on the key
    sorted_list = sorted(item_list, key=lambda k: ("" if k.get(field) is None else k.get(field)))
    # move the item_id ones to the front
    move_list = [i for i in sorted_list if i.get(field) == item_id]
    move_list.reverse()
    for move_item in move_list:
        try:
            sorted_list.remove(move_item)
            sorted_list.insert(0, move_item)
        except:  # pragma: no cover
            pass
    return sorted_list


def fetch_all_items(sheet, field_list, connection):
    """For a given sheet, get all released items"""
    all_items = []
    if sheet in fetch_items.keys():
        # Search all items, get uuids, get them one by one
        obj_id = "search/?type=" + fetch_items[sheet]
        resp = submit_utils.get_FDN(obj_id, connection)
        items_uuids = [i["uuid"] for i in resp['@graph']]
        items_list = []
        for item_uuid in items_uuids:
            items_list.append(submit_utils.get_FDN(item_uuid, connection))

        # order items with lab and user
        # the date ordering is already in place through search result (resp)
        # 1) order by dcic lab
        items_list = sort_item_list(items_list, '/lab/dcic-lab/', 'lab')
        # 2) sort by submitters lab
        items_list = sort_item_list(items_list, connection.lab, 'lab')
        # 3) sort by submitters user
        items_list = sort_item_list(items_list, connection.user, 'submitted_by')
        # 4) If biosurce, also sort by tier
        if sheet == "Biosource":
            items_list = sort_item_list(items_list, 'Tier 1', 'cell_line_tier')

        # filter for fields that exist on the excel sheet
        for item in items_list:
            item_info = []
            for field in field_list:
                # required fields will have a star
                field = field.strip('*')
                # add # to skip existing items during submission
                if field == "#Field Name:":
                    item_info.append("#")
                # the attachment field returns a dictionary
                elif field == "attachment":
                    try:
                        item_info.append(item.get(field)['download'])
                    except:
                        item_info.append("")
                else:
                    # when writing values, check for the lists and turn them into string
                    write_value = item.get(field, '')
                    if isinstance(write_value, list):
                        write_value = ','.join(write_value)
                    item_info.append(write_value)
            all_items.append(item_info)
        return all_items
    else:  # pragma: no cover
        return


def get_field_type(field):
    field_type = field.get('type', '')
    if field_type == 'string':
        if field.get('linkTo', ''):
            return "Item:" + field.get('linkTo')
        # if multiple objects are linked by "anyOf"
        if field.get('anyOf', ''):
            links = list(filter(None, [d.get('linkTo', '') for d in field.get('anyOf')]))
            if links:
                return "Item:" + ' or '.join(links)
        # if not object return string
        return 'string'
    elif field_type == 'array':
        return 'array of ' + get_field_type(field.get('items'))
    return field_type


def is_subobject(field):
    try:
        return field['items']['type'] == 'object'
    except:
        return False


def dotted_field_name(field_name, parent_name=None):
    if parent_name:
        return "%s.%s" % (parent_name, field_name)
    else:
        return field_name


def build_field_list(properties, required_fields=None, include_description=False,
                     include_comment=False, include_enums=False, parent='', is_submember=False):
    fields = []
    for name, props in properties.items():
        is_member_of_array_of_objects = False
        if not props.get('calculatedProperty', False):
            if 'submit4dn' not in props.get('exclude_from', [""]):
                if is_subobject(props):
                    if get_field_type(props).startswith('array'):
                        is_member_of_array_of_objects = True
                    fields.extend(build_field_list(props['items']['properties'],
                                                   required_fields,
                                                   include_description,
                                                   include_comment,
                                                   include_enums,
                                                   name,
                                                   is_member_of_array_of_objects)
                                  )
                else:
                    field_name = dotted_field_name(name, parent)
                    if required_fields is not None:
                        if field_name in required_fields:
                            field_name = '*' + field_name
                    field_type = get_field_type(props)
                    if is_submember:
                        field_type = "array of embedded objects, " + field_type
                    desc = '' if not include_description else props.get('description', '')
                    comm = '' if not include_comment else props.get('comment', '')
                    enum = '' if not include_enums else props.get('enum', '')
                    lookup = props.get('lookup', 500)  # field ordering info
                    # if array of string with enum
                    if field_type == "array of strings":
                        sub_props = props.get('items', '')
                        enum = '' if not include_enums else sub_props.get('enum', '')
                    # copy paste exp set for ease of keeping track of different types in experiment objects
                    fields.append(FieldInfo(field_name, field_type, lookup, desc, comm, enum))
    return fields


def get_uploadable_fields(connection, types, include_description=False,
                          include_comments=False, include_enums=False):
    fields = {}
    for name in types:
        schema_name = name + '.json'
        uri = '/profiles/' + schema_name
        schema_grabber = submit_utils.FDN_Schema(connection, uri)
        required_fields = schema_grabber.required
        fields[name] = build_field_list(schema_grabber.properties,
                                        required_fields,
                                        include_description,
                                        include_comments,
                                        include_enums)
        if name.startswith('Experiment') and not name.startswith('ExperimentSet'):
            fields[name].extend(exp_set_addition)
    return fields


def create_xls(all_fields, filename):
    '''
    fields being a dictionary of sheet -> FieldInfo(objects)
    create one sheet per dictionary item, with three columns of fields
    for fieldname, description and enum
    '''
    wb = xlwt.Workbook()
    # order sheets
    sheet_list = [(sheet, all_fields[sheet]) for sheet in sheet_order if sheet in all_fields.keys()]
    for obj_name, fields in sheet_list:
        ws = wb.add_sheet(obj_name)
        ws.write(0, 0, "#Field Name:")
        ws.write(1, 0, "#Field Type:")
        ws.write(2, 0, "#Description:")
        ws.write(3, 0, "#Additional Info:")
        # order fields in sheet based on lookup numbers, then alphabetically
        for col, field in enumerate(sorted(sorted(fields), key=lambda x: x.lookup)):
            ws.write(0, col+1, str(field.name))
            ws.write(1, col+1, str(field.ftype))
            if field.desc:
                ws.write(2, col+1, str(field.desc))
            # combine comments and Enum
            add_info = ''
            if field.comm:
                add_info += str(field.comm)
            if field.enum:
                add_info += "Choices:" + str(field.enum)
            if not field.comm and not field.enum:
                add_info = "-"
            ws.write(3, col+1, add_info)
    wb.save(filename)


def main():  # pragma: no cover
    args = getArgs()
    key = submit_utils.FDN_Key(args.keyfile, args.key)
    if key.error:
        sys.exit(1)
    connection = submit_utils.FDN_Connection(key)
    # test connection
    if not connection.check:
        print("CONNECTION ERROR: Please check your keys.")
        return

    if not args.remote:
        connection.prompt_for_lab_award()

    if args.type == ['all']:
        args.type = [sheet for sheet in sheet_order if sheet not in [
                    'ExperimentMic_Path', 'OntologyTerm']]
    elif args.type == ['HiC']:
        args.type = [
            "Document", "Protocol", "Publication", "IndividualMouse", "IndividualHuman",
            "Vendor", "Enzyme", "Construct", "TreatmentRnai", "TreatmentChemical",
            "GenomicRegion", "Target", "Modification", "Biosource", "Biosample",
            "BiosampleCellCulture", "Image", "FileFastq", "FileProcessed",
            "ExperimentHiC", "ExperimentSetReplicate",
            ]
    elif args.type.lower() == ['chip-seq']:
        args.type == [
            "Document", "Protocol", "Publication", "IndividualMouse", "IndividualHuman",
            "Vendor", "Enzyme", "Construct", "TreatmentRnai", "TreatmentChemical",
            "GenomicRegion", "Target", "Antibody", "Modification", "Biosource",
            "Biosample", "BiosampleCellCulture", "Image", "FileFastq", "FileProcessed",
            "ExperimentSeq", "ExperimentSetReplicate",
            ]
    elif args.type.lower() == ['repliseq']:
        args.type == [
            "Document", "Protocol", "Publication", "IndividualMouse", "IndividualHuman",
            "Vendor", "Enzyme", "Construct", "TreatmentRnai", "TreatmentChemical",
            "GenomicRegion", "Target", "Antibody", "Modification", "Biosource",
            "Biosample", "BiosampleCellCulture", "Image", "FileFastq", "FileProcessed",
            "ExperimentRepliseq", "ExperimentSetReplicate",
            ]
    elif args.type.upper() == ['FISH']:
        args.type = [
            "Document", "Protocol", "Publication", "IndividualMouse", "IndividualHuman",
            "Vendor", "Construct", "TreatmentRnai", "TreatmentChemical", "GenomicRegion",
            "Target", "Antibody", "Modification", "Biosource", "Biosample", "BiosampleCellCulture",
            "Image", "FileFasta", "FileProcessed", "MicroscopeSettingA1", "FileMicroscopy",
            "FileSetMicroscopeQc", "ImagingPath", "ExperimentMic", "ExperimentSetReplicate",
            ]

    fields = get_uploadable_fields(connection, args.type,
                                   args.descriptions,
                                   args.comments,
                                   args.enums)

    if args.debug:
        print("retrieved fields as")
        from pprint import pprint
        pprint(fields)

    if args.writexls:
        file_name = args.outfile
        create_xls(fields, file_name)


if __name__ == '__main__':
    main()
